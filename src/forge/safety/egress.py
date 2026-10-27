"""Keeps the user's code from leaving the machine through tools that talk to the internet (D-503).

The web tools already refuse internal addresses (tools/web_guard.py); that looks at WHERE a call goes. This looks at WHAT it carries: a search
query, an address, or an MCP argument that repeats code the agent has seen is refused before it is sent. What counts as "the user's code":
- the text files of the workspace's repository copy (Mode A: `repo/`, Mode B: `project/`), indexed on first use;
- everything a local tool returned to the model in this session (a file read, a search hit, a command's output) via `remember`, so code from a
  read-granted folder or pasted into a file is covered too. Results of tools that fetch from the web are never remembered: they are public.

Matching is on token windows, not whole files: 12 consecutive code tokens (words, numbers, punctuation) that also occur in remembered text. Spaces,
line breaks, URL escapes and base64 do not hide a copy. Short queries ("pandas read_csv usecols dtype") cannot match; a pasted function does.
Also refused: several lines of text in a query, very long addresses, and long opaque tokens (encoded data) in an address.

What this does not do: it does not look at commands the model runs in the shell (the permission gate asks about those, always, when they touch the
network) or at code the model writes and runs. See docs/SECURITY_EGRESS.md."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import unquote_plus

WINDOW = 12  # tokens; below this, common idioms match by chance
MIN_CODE_MARKS = 2  # a window must look like code (brackets, operators, snake_case, camelCase), not prose
MAX_INDEX_FILES = 6000
MAX_FILE_BYTES = 400_000
MAX_WINDOWS = 3_000_000  # memory bound: about 100 MB in the worst case
MAX_QUERY_LINES = 3
MAX_QUERY_CHARS = 500
MAX_URL_CHARS = 2000
OPAQUE_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{60,}")  # candidates to decode
ENCODED_RUN = re.compile(r"[A-Za-z0-9+/=]{60,}")  # no hyphens: a long readable slug is not encoded data
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\sA-Za-z0-9_]")
CODE_MARK = re.compile(r"[(){}\[\]=<>:;]|_|[a-z][A-Z]|\d")
SKIP_FOLDERS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".forge",
}
TEXT_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".cs", ".go", ".rs", ".rb", ".php", ".c", ".h", ".cc", ".cpp",
    ".hpp", ".swift", ".scala", ".sql", ".sh", ".ps1", ".bat", ".html", ".htm", ".css", ".scss", ".vue", ".svelte", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".xml", ".md", ".rst", ".txt", ".ipynb", ".tf", ".gradle", ".proto", ".graphql",
}  # fmt: skip


def _windows(text: str) -> Iterable[int]:
    """Hash of every code-like window of WINDOW tokens in the text."""
    tokens = TOKEN.findall(text)
    for start in range(len(tokens) - WINDOW + 1):
        window = tokens[start : start + WINDOW]
        if sum(1 for token in window if CODE_MARK.search(token)) >= MIN_CODE_MARKS:
            yield hash(" ".join(window))


def _decoded_views(text: str) -> list[str]:
    """The text as it could be read after URL unescaping, and any long base64 or hex run inside it decoded."""
    views = [text]
    unescaped = unquote_plus(text)
    if unescaped != text:
        views.append(unescaped)
    for view in list(views):
        for run in OPAQUE_TOKEN.findall(view):
            padded = run + "=" * (-len(run) % 4)
            for decoder in (base64.b64decode, base64.urlsafe_b64decode):
                try:
                    views.append(decoder(padded).decode("utf-8", errors="ignore"))
                except (binascii.Error, ValueError):
                    continue
            if re.fullmatch(r"[0-9a-fA-F]+", run) and len(run) % 2 == 0:
                views.append(bytes.fromhex(run).decode("utf-8", errors="ignore"))
    return views


class EgressGuard:
    def __init__(self, code_root: Path | None = None, extra_roots: Iterable[Path] = ()) -> None:
        self._roots = [root for root in [code_root, *extra_roots] if root is not None]
        self._windows: set[int] = set()
        self._indexed = False
        self.user_addresses: Callable[[], set[str]] | None = None  # addresses the user typed: theirs to send

    def _full(self) -> bool:
        return len(self._windows) >= MAX_WINDOWS

    def remember(self, text: str) -> None:
        """Adds text the model has seen from a local source. Cheap enough to call on every tool result."""
        if self._full() or len(text) < 40:
            return
        self._windows.update(_windows(text))

    def _index(self) -> None:
        if self._indexed:
            return
        self._indexed = True
        files = 0
        for root in self._roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if files >= MAX_INDEX_FILES or self._full():
                    return
                if any(part in SKIP_FOLDERS for part in path.relative_to(root).parts[:-1]):
                    continue
                if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
                    continue
                try:
                    if path.stat().st_size > MAX_FILE_BYTES:
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                files += 1
                self._windows.update(_windows(text))

    def check_text(self, text: str, *, is_address: bool = False, label: str = "text") -> str | None:
        """None when the text may leave the machine, else the reason it may not."""
        if is_address and self.user_addresses is not None and text in self.user_addresses():
            return None
        if is_address and len(text) > MAX_URL_CHARS:
            return f"the {label} is {len(text)} characters long; an address that long can carry data. Use a shorter one"
        if not is_address and (len(text) > MAX_QUERY_CHARS or text.count("\n") >= MAX_QUERY_LINES):
            return (
                f"the {label} is long or has several lines, which looks like pasted text; "
                f"send a short plain-words {label} instead"
            )
        self._index()
        for view in _decoded_views(text):
            if any(window in self._windows for window in _windows(view)):
                return (
                    f"the {label} repeats code from the user's project, and code is never sent to a web service. "
                    f"Describe the problem in your own words (library name, error message, concept) without the project's code"
                )
        if is_address and any(_mixed(run) for run in ENCODED_RUN.findall(text)):
            return f"the {label} contains a long encoded-looking string, which could be hidden data; do not put one in an address"
        return None

    def check_arguments(self, tool: str, arguments: dict[str, object]) -> str | None:
        """Checks every text value of a tool call. Fields named url/uri/href are treated as addresses."""
        for key, value in _strings(arguments):
            address = key.rsplit(".", 1)[-1].lower() in {
                "url",
                "uri",
                "href",
                "link",
                "source_url",
            } or value.startswith(("http://", "https://"))
            problem = self.check_text(value, is_address=address, label=f"'{key}' argument of {tool}")
            if problem:
                return problem
        return None


def _mixed(run: str) -> bool:
    """Digits and both letter cases in one long run: encoded data, not a readable path."""
    return bool(re.search(r"\d", run) and re.search(r"[a-z]", run) and re.search(r"[A-Z]", run))


def _strings(value: object, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix or "value", value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            yield from _strings(item, f"{prefix}[{index}]")
