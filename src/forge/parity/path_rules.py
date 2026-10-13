"""Path-scoped rules (TODO C12 b, D-297). A big repository's rules should not all sit in the context all the time. A rule file
`rules/<name>.md` with a `paths:` list in its front matter is shown to the model only when it first touches a file that matches:

    ---
    paths: ["backend/**/*.py", "*.sql"]
    ---
    Use the repository helpers in backend/db.py; never write raw SQL in a route.

Rule folders (later ones add to earlier ones): `<forge home>/rules` (every project), the repository-level folder's `rules` (this
repository or host profile), and `<workspace>/.forge/rules` (this requirement). Each rule is delivered once per session, appended to
the result of the tool call that touched the file. A rule without `paths` is ignored here (put always-on text in FORGE.md)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from forge.llm.tokens import head_and_tail

RULE_TOKEN_CAP = 600
MAX_RULES_PER_CALL = 4


@dataclass(frozen=True)
class Rule:
    name: str
    patterns: tuple[str, ...]
    text: str


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """`**` crosses folders, `*` and `?` stay inside one folder level; a pattern without a slash matches in any folder."""
    pattern = pattern.replace("\\", "/").lstrip("./")
    anywhere = "/" not in pattern
    out = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        out.append("[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char))
        index += 1
    body = "".join(out)
    return re.compile(("(?:.*/)?" if anywhere else "") + body + r"\Z", re.IGNORECASE)


def _unquote(item: str) -> str:
    return item.strip().strip("\"'").strip()


def parse_rule(name: str, text: str) -> Rule | None:
    """A rule from the file's text; None when it has no `paths` or no body. `paths` may be a flow list (["a", b]), a comma
    separated line, or a block list (one `- pattern` per line)."""
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.DOTALL)
    if match is None:
        return None
    header, body = match.group(1), match.group(2).strip()
    paths_line = re.search(r"^paths[ \t]*:[ \t]*(.*)$", header, re.MULTILINE)
    if paths_line is None or not body:
        return None
    raw = paths_line.group(1).strip()
    if raw:
        items = raw.removeprefix("[").removesuffix("]").split(",")
    else:  # a block list under `paths:`
        block = re.search(r"^paths[ \t]*:[ \t]*\n((?:[ \t]*-[ \t]*.+\n?)+)", header + "\n", re.MULTILINE)
        items = [line.strip().removeprefix("-") for line in block.group(1).splitlines()] if block else []
    patterns = tuple(p for p in (_unquote(i) for i in items) if p)
    return Rule(name, patterns, body) if patterns else None


class PathRules:
    """The rules found in the given folders, and which of them were already delivered in this session."""

    def __init__(self, folders: list[Path]) -> None:
        self.folders = folders
        self._entries: list[tuple[Rule, list[re.Pattern[str]]]] | None = None
        self._delivered: set[int] = set()

    def reload(self) -> None:
        self._entries = None

    def rules(self) -> list[Rule]:
        return [rule for rule, _ in self._load()]

    def _load(self) -> list[tuple[Rule, list[re.Pattern[str]]]]:
        if self._entries is None:
            entries: list[tuple[Rule, list[re.Pattern[str]]]] = []
            for folder in self.folders:
                try:
                    files = sorted(folder.glob("*.md"))
                except OSError:
                    continue
                for file in files:
                    try:
                        rule = parse_rule(file.stem, file.read_text(encoding="utf-8"))
                    except (OSError, UnicodeError):
                        continue
                    if rule is not None:
                        entries.append((rule, [glob_to_regex(pattern) for pattern in rule.patterns]))
            self._entries = entries
        return self._entries

    def for_path(self, path: str) -> list[Rule]:
        """Rules matching this file that have not been delivered yet (marks them delivered)."""
        relative = path.replace("\\", "/").lstrip("/")
        hits: list[Rule] = []
        for number, (rule, patterns) in enumerate(self._load()):
            if number not in self._delivered and any(p.match(relative) for p in patterns):
                self._delivered.add(number)
                hits.append(rule)
        return hits[:MAX_RULES_PER_CALL]

    def note_for(self, path: str) -> str:
        """The text to append to a tool result for this path, or an empty string."""
        rules = self.for_path(path)
        if not rules:
            return ""
        parts = []
        for rule in rules:
            head, tail, omitted = head_and_tail(rule.text, RULE_TOKEN_CAP)
            cut = f"\n[... {omitted} tokens omitted ...]\n{tail}" if omitted else ""
            parts.append(f"Rule '{rule.name}':\n{head}{cut}")
        intro = f"\n\n[Rules that apply to {path} (follow them for files like this):\n"
        return intro + "\n\n".join(parts) + "\n]"
