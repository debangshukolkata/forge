"""The host symbols the delivered code imports, found from the code itself (DECISIONS D-112).

Seen live: the agent never wrote INTERFACE_CONTRACT, and the export's default text then claimed "the new code
relies on no host symbols" while it called the host's `payments.audit.log_event`. A symbol counts as a host
symbol when its package is one the project shares with the host (a top-level package present in project/ or
_harness/host_stubs/) and the module isn't new code in project/. Its signature comes from the harness stub.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from forge.workspace.workspace import Workspace


@dataclass(frozen=True)
class HostSymbol:
    module: str
    name: str
    signature: str  # "def log_event(event: str, **fields: object) -> None", or "" when not stubbed

    def render(self) -> str:
        where = f"`from {self.module} import {self.name}`"
        if not self.signature:
            return f"- {where} (no stub: signature unknown)"
        return f"- {where}: `{self.signature}`"


def host_symbols_used(workspace: Workspace, delivered: list[str]) -> list[HostSymbol]:
    project, stubs = workspace.repo_dir, workspace.harness_dir / "host_stubs"
    shared = {p.name for root in (project, stubs) if root.is_dir() for p in root.iterdir() if p.is_dir()}
    found: dict[tuple[str, str], HostSymbol] = {}
    for relative in delivered:
        path = project / relative
        if path.suffix != ".py" or path.name.startswith("test_") or "tests" in Path(relative).parts:
            continue
        tree = _parse(path)
        for node in ast.walk(tree) if tree else []:
            if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
                continue
            if node.module.split(".")[0] not in shared or _module_file(project, node.module):
                continue
            stub = _module_file(stubs, node.module)
            for alias in node.names:
                key = (node.module, alias.name)
                if key not in found:
                    found[key] = HostSymbol(node.module, alias.name, _signature(stub, alias.name))
    return sorted(found.values(), key=lambda s: (s.module, s.name))


def contract_with_host_symbols(contract: str, symbols: list[HostSymbol]) -> str:
    """The agent's contract, plus any host symbol it doesn't mention; a generated one when there is none."""
    if not contract.strip():
        if not symbols:
            return "# Interface contract\n\nThe new code imports no host symbols.\n"
        lines = [
            "# Interface contract",
            "",
            "The new code relies on these existing host symbols (detected by",
        ]
        lines += ["Forge from the imports; signatures from the stand-ins it was tested against):", ""]
        return "\n".join([*lines, *(s.render() for s in symbols), ""])
    missing = [s for s in symbols if s.name not in contract]
    if not missing:
        return contract
    extra = ["", "## Also used (detected by Forge from the imports)", "", *(s.render() for s in missing), ""]
    return contract.rstrip("\n") + "\n" + "\n".join(extra)


def _module_file(root: Path, module: str) -> Path | None:
    base = root.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _signature(stub: Path | None, name: str) -> str:
    tree = _parse(stub) if stub else None
    for node in tree.body if tree else []:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            return f"{prefix} {name}({ast.unparse(node.args)}){returns}"
        if isinstance(node, ast.ClassDef) and node.name == name:
            return f"class {name}"
    return ""


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
