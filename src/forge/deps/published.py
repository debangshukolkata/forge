"""What is published of a Python library: its releases, and the code of any one of them (D-642).

A release's wheel is read as text (`ast`), never installed, imported or run. Only library names and versions leave the
machine. The source is PyPI; where that cannot be reached the tool falls back to pip, which knows the company's index."""

from __future__ import annotations

import ast
import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

PYPI = "https://pypi.org"
TIMEOUT_S = 30.0
MAX_WHEEL_BYTES = 60_000_000
MAX_SOURCE_BYTES = 2_000_000
MAX_HOPS = 6
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}")
VERSION = re.compile(r"[0-9][0-9A-Za-z.+!-]{0,40}")
FINAL = re.compile(r"\d+(\.\d+)*(\.post\d+)?")
ClientFactory = Callable[[], httpx.Client]


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True)


@dataclass(frozen=True)
class Release:
    version: str
    date: str = ""
    requires_python: str = ""
    yanked: bool = False
    wheel_url: str = ""


@dataclass
class Published:
    name: str
    releases: list[Release] = field(default_factory=list)  # oldest first; pre-releases left out
    requires: list[str] = field(default_factory=list)  # of the latest release


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def line_of(version: str) -> str:
    """The line a release belongs to: 1.5.2 -> 1.5 (a minor release of a library under 1.0 can break as well)."""
    return ".".join(version.split(".")[:2])


def fetch_published(name: str, client_factory: ClientFactory = _client) -> Published:
    if not NAME.fullmatch(name):
        raise ValueError(f"not a package name: {name!r}")
    with client_factory() as client:
        answer = client.get(f"{PYPI}/pypi/{name}/json")
        answer.raise_for_status()
        data = answer.json()
    found: list[Release] = []
    for version, files in (data.get("releases") or {}).items():
        if not files or not FINAL.fullmatch(version):
            continue
        wheel = next((f for f in files if str(f.get("filename", "")).endswith("none-any.whl")), None)
        found.append(
            Release(
                version,
                str(files[0].get("upload_time", ""))[:10],
                str(files[0].get("requires_python") or ""),
                all(bool(f.get("yanked")) for f in files),
                str(wheel.get("url", "")) if wheel else "",
            )
        )
    found.sort(key=lambda release: version_key(release.version))
    requires = [r for r in (data.get("info") or {}).get("requires_dist") or [] if "extra ==" not in r]
    return Published(name, found, requires)


def pick_release(published: Published, wanted: str) -> Release | None:
    """`latest`, an exact version, or a line such as 0.3 (its newest release)."""
    usable = [r for r in published.releases if not r.yanked]
    if wanted in ("", "latest"):
        return usable[-1] if usable else None
    exact = next((r for r in published.releases if r.version == wanted), None)
    if exact is not None:
        return exact
    return next((r for r in reversed(usable) if r.version.startswith(wanted.rstrip(".") + ".")), None)


def fetch_wheel(url: str, client_factory: ClientFactory = _client) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("the release has no pure Python wheel to read")
    chunks: list[bytes] = []
    size = 0
    with client_factory() as client, client.stream("GET", url) as answer:
        answer.raise_for_status()
        for chunk in answer.iter_bytes():
            size += len(chunk)
            if size > MAX_WHEEL_BYTES:
                raise ValueError("the wheel is too large to read")
            chunks.append(chunk)
    return b"".join(chunks)


class WheelCode:
    """Looks names up in the source of a wheel."""

    def __init__(self, data: bytes) -> None:
        self._zip = zipfile.ZipFile(io.BytesIO(data))
        self._names = set(self._zip.namelist())

    def module_path(self, module: str) -> str | None:
        base = module.replace(".", "/")
        return next((p for p in (f"{base}/__init__.py", f"{base}.py") if p in self._names), None)

    def tree(self, module: str) -> ast.Module | None:
        path = self.module_path(module)
        if path is None or self._zip.getinfo(path).file_size > MAX_SOURCE_BYTES:
            return None
        try:
            return ast.parse(self._zip.read(path).decode("utf-8", "replace"))
        except SyntaxError:
            return None

    def describe(self, dotted: str) -> str:
        """The symbol as this release has it: where it is, its signature, whether it is deprecated."""
        parts = dotted.split(".")
        for cut in range(len(parts), 0, -1):
            module = ".".join(parts[:cut])
            if self.module_path(module) is None:
                continue
            rest = parts[cut:]
            if not rest:
                return self._describe_module(module)
            return self._describe_name(module, rest, MAX_HOPS)
        return f"NOT IN THIS PACKAGE: {dotted}. Its modules: {', '.join(self._top_modules())}"

    def _top_modules(self) -> list[str]:
        tops = {
            "/".join(n.split("/")[:2]).removesuffix(".py").replace("/", ".")
            for n in self._names
            if n.endswith(".py") and ".dist-info" not in n
        }
        return sorted(t for t in tops if not t.endswith("__init__"))[:60]

    def _describe_module(self, module: str) -> str:
        tree = self.tree(module)
        names = sorted(self._public_names(tree)) if tree else []
        return f"module {module}; names: {', '.join(names[:120]) or 'none'}"

    @staticmethod
    def _exports(tree: ast.Module) -> set[str]:
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else []
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                value = node.value  # type: ignore[attr-defined]
                if isinstance(value, ast.List | ast.Tuple):
                    return {
                        e.value
                        for e in value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    }
        return set()

    def _public_names(self, tree: ast.Module) -> set[str]:
        found = self._exports(tree)
        for node in tree.body:
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                and node.name[0] != "_"
            ):
                found.add(node.name)
        return found

    def _describe_name(self, module: str, rest: list[str], hops: int) -> str:
        tree = self.tree(module)
        if tree is None:
            return f"{module} cannot be read in this release."
        name = rest[0]
        definitions: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            if node.name == name and (node in tree.body or isinstance(node, ast.ClassDef)):
                definitions.append(node)
        if definitions:
            return _definition_text(module, definitions, rest[1:])
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                if (alias.asname or alias.name) != name:
                    continue
                target = self._import_target(module, node)
                if self.module_path(target) is None:
                    return f"{module}.{name} is re-exported from {target}, which is another package: look it up there."
                if hops <= 0:
                    return f"{module}.{name} is re-exported from {target}."
                if self.module_path(f"{target}.{alias.name}") is not None and len(rest) > 1:
                    return self._describe_name(f"{target}.{alias.name}", rest[1:], hops - 1)
                return self._describe_name(target, [alias.name, *rest[1:]], hops - 1)
        for node in tree.body:
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                return f"{module}.{name}: {ast.unparse(node)[:300]}"
        if name in self._exports(tree):
            return f"{module}.{name} is exported, but loaded lazily: its definition is in another module or package."
        names = sorted(self._public_names(tree))
        return (
            f"DOES NOT EXIST in this release: {module}.{name}. Names there: {', '.join(names[:80]) or 'none'}"
        )

    def _import_target(self, module: str, node: ast.ImportFrom) -> str:
        if not node.level:
            return node.module or ""
        path = self.module_path(module) or ""
        package = module.split(".") if path.endswith("__init__.py") else module.split(".")[:-1]
        package = package[: len(package) - (node.level - 1)]
        return ".".join([*package, *([node.module] if node.module else [])])


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{node.name}({ast.unparse(node.args)}){returns}"


def _notes(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    marks = [ast.unparse(d)[:400] for d in node.decorator_list if "deprecat" in ast.unparse(d).lower()]
    doc = (ast.get_docstring(node) or "").strip()
    text = "".join(f"\nDEPRECATED: {mark}" for mark in marks)
    if not marks and "deprecated" in doc[:600].lower():
        text += "\nIts documentation calls it deprecated."
    return text + (f"\n{doc[:900]}" if doc else "")


def _definition_text(
    module: str, nodes: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef], rest: list[str]
) -> str:
    node = nodes[-1]  # overloads come first, the real one last
    if isinstance(node, ast.ClassDef):
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
        if rest:
            found = [m for m in methods if m.name == rest[0]]
            if not found:
                return (
                    f"{module}.{node.name} does not define {rest[0]} itself (it may inherit it). It defines: "
                    + ", ".join(m.name for m in methods)
                )
            return f"{module}.{node.name}.{_signature(found[-1])}{_notes(found[-1])}"
        fields = [ast.unparse(n)[:120] for n in node.body if isinstance(n, ast.AnnAssign)]
        lines = [f"class {module}.{node.name}({', '.join(ast.unparse(b) for b in node.bases)}){_notes(node)}"]
        lines += [f"  {text}" for text in fields[:40]]
        lines += [f"  {_signature(m)[:400]}" for m in methods if m.name == "__init__" or m.name[0] != "_"][
            :40
        ]
        return "\n".join(lines)
    return f"{module}.{_signature(node)}{_notes(node)}"
