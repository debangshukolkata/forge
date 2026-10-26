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
import importlib, importlib.util, json, sys, types
root = sys.argv[1]
requests = json.load(sys.stdin)
problems = []
for item in requests:
    module, names, where = item["module"], item["names"], item["where"]
    chains = item.get("chains", [])
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
    if not names and not chains:
        continue
    try:
        loaded = importlib.import_module(module)
    except Exception:
        continue  # a library that needs setup to import is not an invented one
    for chain in chains:  # `alias.a.b` written in the code, followed step by step while the object is a module
        current, label = loaded, module
        if chain["bound"]:
            current = getattr(loaded, chain["bound"], None)
            label = module + "." + chain["bound"]
        for part in chain["parts"]:
            if not isinstance(current, types.ModuleType):
                break
            if hasattr(current, part):
                current = getattr(current, part)
                label += "." + part
                continue
            try:
                current = importlib.import_module(current.__name__ + "." + part)
                label += "." + part
                continue
            except Exception:
                problems.append(f"{where.split(':')[0]}:{chain['line']}: '{label}' has no attribute '{part}'")
                break
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


def _rebound_names(tree: ast.AST) -> set[str]:
    """Names the file assigns, takes as arguments or defines: an `alias.attr` on one of them may not be the module, so it is never checked."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store | ast.Del):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
    return names


def _attribute_chains(tree: ast.AST, binding: str) -> list[dict[str, object]]:
    """Every `binding.a.b` written in the file as its parts (at most three deep), with the line it starts on."""
    found: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name) and current.id == binding:
            parts.reverse()
            if node.lineno and not any(
                f["line"] == node.lineno and f["parts"] == parts[:3] for f in found
            ):  # the outer chain is seen first; its inner prefixes are the same chain
                found.append({"parts": parts[:3], "line": node.lineno})
    return found


def collect_imports(root: Path, only: set[Path] | None = None) -> list[dict[str, object]]:
    """Absolute imports as resolver requests, from the project's Python files (all of them count as local names;
    only the files in `only`, when given, are read for imports)."""
    requests: dict[tuple[str, str], dict[str, object]] = {}
    files = [p for p in root.rglob("*.py") if not SKIPPED_FOLDERS.intersection(p.relative_to(root).parts)]
    # Any file or folder name in the project may be a module reached through a src/ layout, a conftest path or
    # PYTHONPATH, so those top-level names are never reported (only third-party and invented ones are).
    local_names = {p.stem for p in files} | {part for p in files for part in p.relative_to(root).parts[:-1]}
    for path in sorted(files)[:MAX_FILES]:
        if only is not None and path.resolve() not in only:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError, OSError):
            continue
        guarded = _guarded_lines(tree)
        rebound = _rebound_names(tree)
        where_prefix = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if node.__class__ not in (ast.Import, ast.ImportFrom) or node.lineno in guarded:
                continue
            where = f"{where_prefix}:{node.lineno}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in local_names:
                        continue
                    binding = alias.asname or (alias.name if "." not in alias.name else "")
                    chains = (
                        [{"bound": "", **c} for c in _attribute_chains(tree, binding)]
                        if binding and binding not in rebound
                        else []
                    )
                    if chains:
                        requests[(alias.name, where)] = {
                            "module": alias.name,
                            "names": [],
                            "where": where,
                            "chains": chains,
                        }
                    else:
                        requests.setdefault(
                            (alias.name, ""), {"module": alias.name, "names": [], "where": where}
                        )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
                and node.module.split(".")[0] not in local_names
            ):
                key = (node.module, where)
                chains = [
                    {"bound": alias.name, **c}
                    for alias in node.names
                    if alias.name != "*" and (alias.asname or alias.name) not in rebound
                    for c in _attribute_chains(tree, alias.asname or alias.name)
                ]
                requests[key] = {
                    "module": node.module,
                    "names": [alias.name for alias in node.names],
                    "where": where,
                    "chains": chains,
                }
    return list(requests.values())


def import_problems(
    root: Path, python: str, env: dict[str, str] | None = None, only: set[Path] | None = None
) -> list[str]:
    """Findings such as "app/routes.py:3: no module named 'flask_magic'"; empty when everything resolves or the
    check could not run."""
    requests = collect_imports(root, only)
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
            env=env,
        )
        found = json.loads(run.stdout.strip().splitlines()[-1]) if run.stdout.strip() else []
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return []
    return list(
        dict.fromkeys(str(item) for item in found)
    )  # a chain and its own prefix report the same fault once


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
