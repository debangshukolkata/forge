"""Compare two DESIGN.md files (D-348): which tokens were added, removed or changed, and whether the new file is worse."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge.designsystem.lint import Finding, lint_system
from forge.designsystem.spec import TOKEN_GROUPS, DesignSystem


@dataclass
class Change:
    kind: str  # "added", "removed" or "changed"
    path: str
    before: Any = None
    after: Any = None


@dataclass
class DesignDiff:
    changes: list[Change] = field(default_factory=list)
    new_findings: list[Finding] = field(
        default_factory=list
    )  # lint findings the new file has and the old one did not
    regression: bool = False


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            _flatten(f"{prefix}.{key}", inner, out)
    else:
        out[prefix] = value


def tokens(system: DesignSystem) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for group in TOKEN_GROUPS:
        _flatten(group, system.group(group), flat)
    return flat


def diff_systems(before: DesignSystem, after: DesignSystem) -> DesignDiff:
    old, new = tokens(before), tokens(after)
    result = DesignDiff()
    for path in sorted(old.keys() | new.keys()):
        if path not in old:
            result.changes.append(Change("added", path, None, new[path]))
        elif path not in new:
            result.changes.append(Change("removed", path, old[path], None))
        elif old[path] != new[path]:
            result.changes.append(Change("changed", path, old[path], new[path]))
    seen = {(f.rule, f.path) for f in lint_system(before)}
    result.new_findings = [
        f for f in lint_system(after) if (f.rule, f.path) not in seen and f.severity != "info"
    ]
    result.regression = any(f.severity == "error" for f in result.new_findings)
    return result


def describe_diff(result: DesignDiff, limit: int = 60) -> str:
    if not result.changes and not result.new_findings:
        return "No token changes and no new findings."
    lines = [f"{len(result.changes)} token change(s):"]
    for change in result.changes[:limit]:
        if change.kind == "changed":
            lines.append(f"  changed {change.path}: {change.before} -> {change.after}")
        elif change.kind == "added":
            lines.append(f"  added   {change.path}: {change.after}")
        else:
            lines.append(f"  removed {change.path} (was {change.before})")
    if result.new_findings:
        regression = " (REGRESSION: new errors)" if result.regression else ""
        lines.append(f"{len(result.new_findings)} new finding(s) in the new file{regression}:")
        lines += [
            f"  {f.severity.upper()} [{f.rule}] {f.path}: {f.message}" for f in result.new_findings[:20]
        ]
    return "\n".join(lines)
