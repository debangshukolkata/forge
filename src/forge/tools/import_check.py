"""Import check (TODO C8): the model sometimes imports a package that does not exist or a name a library does not
have. Reading the project's own `import` lines and resolving each against the workspace's real environment finds
those before the task is called done. Never raises: when the check cannot run it says nothing."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

SKIPPED_FOLDERS = {
    "node_modules",
    "dist",
    "build",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".forge",
    "_harness",
}
MAX_FILES = 300
MAX_FINDINGS_SHOWN = 8
CHECK_TIMEOUT_S = 60

# Runs inside the workspace's own interpreter, so it sees exactly the packages the app will see.
RESOLVER = r"""
import importlib, importlib.util, json, sys
root = sys.argv[1]
requests = json.load(sys.stdin)
problems = []
for item in requests:
    module, names, where = item["module"], item["names"], item["where"]
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError, AttributeError):
        spec = None
    if spec is None:
        problems.append(f"{where}: no module named '{module}'")
        continue
    origin = getattr(spec, "origin", None) or ""
    if origin.startswith(root):
        continue  # the project's own module: importing it could run application code
    if not names:
        continue
    try:
        loaded = importlib.import_module(module)
    except Exception:
        continue  # a library that needs setup to import is not an invented one
    for name in names:
        if name == "*" or hasattr(loaded, name):
            continue
        try:
            if importlib.util.find_spec(module + "." + name) is not None:
                continue
        except Exception:
            pass
        problems.append(f"{where}: '{module}' has no name '{name}'")
print(json.dumps(problems))
"""


def _guarded_lines(tree: ast.AST) -> set[int]:
    """Lines of imports that are allowed to fail or that only exist for type checkers."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            catches_import_error = any(
                handler.type is None
                or any(
                    isinstance(part, ast.Name)
                    and part.id in {"ImportError", "ModuleNotFoundError", "Exception"}
                    for part in ast.walk(handler.type)
                )
                for handler in node.handlers
            )
            if catches_import_error:
                for child in node.body:
                    guarded.update(range(child.lineno, (child.end_lineno or child.lineno) + 1))
        elif isinstance(node, ast.If) and "TYPE_CHECKING" in ast.dump(node.test):
            for child in node.body:
                guarded.update(range(child.lineno, (child.end_lineno or child.lineno) + 1))
    return guarded


def collect_imports(root: Path) -> list[dict[str, object]]:
    """Absolute imports from the project's Python files, as resolver requests."""
    requests: dict[tuple[str, str], dict[str, object]] = {}
    files = [p for p in root.rglob("*.py") if not SKIPPED_FOLDERS.intersection(p.relative_to(root).parts)]
    for path in sorted(files)[:MAX_FILES]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError, OSError):
            continue
        guarded = _guarded_lines(tree)
        where_prefix = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if node.__class__ not in (ast.Import, ast.ImportFrom) or node.lineno in guarded:
                continue
            where = f"{where_prefix}:{node.lineno}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    key = (alias.name, "")
                    requests.setdefault(key, {"module": alias.name, "names": [], "where": where})
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                key = (node.module, where)
                requests[key] = {
                    "module": node.module,
                    "names": [alias.name for alias in node.names],
                    "where": where,
                }
    return list(requests.values())


def import_problems(root: Path, python: str) -> list[str]:
    """Findings such as "app/routes.py:3: no module named 'flask_magic'"; empty when everything resolves or the
    check could not run."""
    requests = collect_imports(root)
    if not requests:
        return []
    try:
        run = subprocess.run(
            [python, "-c", RESOLVER, str(root.resolve())],
            input=json.dumps(requests),
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_S,
            cwd=root,
        )
        found = json.loads(run.stdout.strip().splitlines()[-1]) if run.stdout.strip() else []
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return []
    return [str(item) for item in found]


def import_note(problems: list[str]) -> str:
    shown = "\n".join(f"- {line}" for line in problems[:MAX_FINDINGS_SHOWN])
    more = (
        f"\n- ... and {len(problems) - MAX_FINDINGS_SHOWN} more" if len(problems) > MAX_FINDINGS_SHOWN else ""
    )
    return (
        "Not accepted: some imports do not resolve in this project's environment, which usually means an invented "
        f"package or name:\n{shown}{more}\nCheck the real package name and installed version (`python -m pip show "
        '<package>`, `python -m pip install <package>` if it is missing, or `python -c "import <module>; '
        'print(dir(<module>))"`), use the standard library when it is enough, fix the imports and call '
        "task_update again."
    )
