"""Module boundaries (D-152): a package may import only from packages in an earlier tier, and the
`Depends on` line of its MODULE.md must list every package it actually imports. This is what keeps a bug in
one module from reaching another. Imports under `if TYPE_CHECKING` are ignored (no runtime dependency)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parent.parent / "src" / "forge"

# Earlier tier = lower level. A package may import only from strictly earlier tiers.
TIERS: list[set[str]] = [
    {"__init__", "buildinfo", "errors", "net"},
    {"safety"},
    {"config", "protocol", "workspace"},
    {"llm", "memory"},
    {"context", "toolkit"},
    {"db", "parity", "vision"},
    {"doctor"},
    {"modeb"},
    {"tools"},
    {"agent"},
    {"subagents"},
    {"workflow"},
    {"diagnose"},
    {"engine"},
    {"session", "ui"},
    {"web"},
    {"cli"},
]
TIER_OF = {name: number for number, names in enumerate(TIERS) for name in names}
DATA_ONLY = {"data", "defaults", "skills", "__pycache__"}  # package data, no code


def _package_of(path: Path) -> str:
    parts = path.relative_to(SOURCE).parts
    return parts[0][:-3] if len(parts) == 1 else parts[0]


def _runtime_imports() -> dict[str, dict[str, str]]:
    """package -> {imported package: first file that imports it}"""
    found: dict[str, dict[str, str]] = {}
    for file in SOURCE.rglob("*.py"):
        package = _package_of(file)
        tree = ast.parse(file.read_text(encoding="utf-8"))
        type_only = {
            id(inner)
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test)
            for statement in node.body
            for inner in ast.walk(statement)
        }
        for node in ast.walk(tree):
            if id(node) in type_only:
                continue
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                parts = name.split(".")
                if parts[0] == "forge" and len(parts) > 1 and parts[1] != package:
                    found.setdefault(package, {}).setdefault(parts[1], str(file.relative_to(SOURCE)))
    return found


def test_every_package_has_a_tier() -> None:
    packages = {_package_of(f) for f in SOURCE.rglob("*.py")} - DATA_ONLY
    assert packages <= set(TIER_OF), (
        f"assign a tier in tests/test_module_boundaries.py: {packages - set(TIER_OF)}"
    )


def test_imports_only_go_to_earlier_tiers() -> None:
    violations = [
        f"{package} (tier {TIER_OF[package]}) imports {target} (tier {TIER_OF[target]}) in {where}"
        for package, targets in _runtime_imports().items()
        for target, where in targets.items()
        if target in TIER_OF and TIER_OF[target] >= TIER_OF[package]
    ]
    assert not violations, "\n".join(violations)


def _declared_dependencies(package: str) -> set[str] | None:
    doc = SOURCE / package / "MODULE.md"
    if not doc.exists():
        return None
    match = re.search(r"\*\*Depends on:\*\* (.+)", doc.read_text(encoding="utf-8"))
    assert match, f"{doc} has no 'Depends on' line"
    text = match.group(1).strip()
    return set() if text.startswith("(none)") else {name.strip() for name in text.split(",")}


@pytest.mark.parametrize("package", sorted(p for p in TIER_OF if (SOURCE / p).is_dir()))
def test_module_doc_lists_real_dependencies(package: str) -> None:
    declared = _declared_dependencies(package)
    assert declared is not None, f"src/forge/{package}/MODULE.md is missing (see docs/MODULES.md)"
    actual = set(_runtime_imports().get(package, {}))
    assert actual <= declared, (
        f"{package} imports {sorted(actual - declared)} but MODULE.md doesn't list them"
    )
    assert all(TIER_OF[d] < TIER_OF[package] for d in declared if d in TIER_OF), (
        f"{package}: MODULE.md lists a dependency from the same or a later tier"
    )
