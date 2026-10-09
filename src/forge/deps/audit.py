"""Vulnerability source 2: pip-audit, the Python Packaging Authority's tool, which checks against PyPI's own
advisory data (D-238). It is an optional extra (`pip install forge[audit]`); without it this source says so.
Python libraries only. Only library names and versions are written to a temporary file and sent."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from forge.deps.model import SOURCE_PIP_AUDIT, Dependency, Finding, SourceStatus

TIMEOUT_S = 300
_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")  # a name pip-audit can read as a requirement
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _reason(done: subprocess.CompletedProcess[str]) -> str:
    """The line that says what went wrong: pip-audit's ERROR line, else the last non-blank line."""
    lines = [line.strip() for line in (done.stderr or done.stdout).splitlines() if line.strip()]
    errors = [line for line in lines if "ERROR" in line or "Error" in line]
    return (errors or lines or ["no output"])[0][:300]


def available() -> bool:
    return importlib.util.find_spec("pip_audit") is not None


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT_S, check=False)


def _parse(report: dict[str, Any], by_name: dict[str, Dependency]) -> list[Finding]:
    findings = []
    for item in report.get("dependencies", []):
        dependency = by_name.get(str(item.get("name", "")).lower().replace("_", "-"))
        for vuln in item.get("vulns", []):
            vuln_id = str(vuln["id"])
            findings.append(
                Finding(
                    id=vuln_id,
                    aliases=[str(alias) for alias in vuln.get("aliases", [])],
                    package=dependency.name if dependency else str(item["name"]),
                    ecosystem="PyPI",
                    version=str(item.get("version", "")),
                    summary=str(vuln.get("description", ""))[:300],
                    fixed_in=[str(v) for v in vuln.get("fix_versions", []) if len(str(v)) != 40],
                    link=f"https://osv.dev/vulnerability/{vuln_id}",
                    found_by=[SOURCE_PIP_AUDIT],
                )
            )
    return findings


def check(dependencies: list[Dependency], runner: Runner | None = None) -> tuple[list[Finding], SourceStatus]:
    """Never raises: any failure becomes the status."""
    python = [d for d in dependencies if d.ecosystem == "PyPI" and d.version and _SAFE.fullmatch(d.name)]
    if runner is None and not available():
        return [], SourceStatus(
            name=SOURCE_PIP_AUDIT,
            status="not_installed",
            detail="pip-audit is not installed. Install it with: pip install pip-audit (or forge[audit]).",
        )
    if not python:
        return [], SourceStatus(
            name=SOURCE_PIP_AUDIT, status="skipped", detail="No Python library with a known version."
        )
    with tempfile.TemporaryDirectory(prefix="forge-audit-") as scratch:
        requirements = Path(scratch) / "requirements.txt"
        requirements.write_text("".join(f"{d.name}=={d.version}\n" for d in python), encoding="utf-8")
        command = [
            sys.executable, "-m", "pip_audit", "-r", str(requirements), "--no-deps", "--disable-pip",
            "--format", "json", "--progress-spinner", "off",
        ]  # fmt: skip
        try:
            done = (runner or _run)(command)
        except (OSError, subprocess.SubprocessError) as error:
            return [], SourceStatus(
                name=SOURCE_PIP_AUDIT, status="unavailable", detail=f"pip-audit did not run: {error}"
            )
    try:
        report = json.loads(done.stdout)  # exit code 1 only means "vulnerabilities found"
    except ValueError:
        return [], SourceStatus(
            name=SOURCE_PIP_AUDIT, status="unavailable", detail=f"pip-audit failed: {_reason(done)}"
        )
    by_name = {d.name.lower().replace("_", "-"): d for d in python}
    findings = _parse(report, by_name)
    return findings, SourceStatus(
        name=SOURCE_PIP_AUDIT, status="ok", checked=len(python), found=len(findings)
    )
