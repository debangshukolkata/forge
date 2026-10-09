"""The shapes the dependency section works with (D-238): a library found in a project, a known vulnerability,
and what each vulnerability source said."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

Ecosystem = Literal["PyPI", "npm"]
SOURCE_OSV = "osv.dev"
SOURCE_PIP_AUDIT = "pip-audit"


def normalise(name: str) -> str:
    """PEP 503 name: case-insensitive, runs of - _ . are the same."""
    return re.sub(r"[-_.]+", "-", name).lower()


class Dependency(BaseModel):
    name: str
    ecosystem: Ecosystem
    version: str | None = None  # None: not pinned anywhere and not installed, so it cannot be checked
    spec: str = ""  # what the manifest asks for, e.g. ">=1.2,<2"
    direct: bool = True  # named in a manifest, as opposed to pulled in by another library
    dev: bool = False  # development-only (dev/test groups, devDependencies)
    file: str = ""  # where it was found, relative to the project

    @property
    def key(self) -> str:
        return f"{self.ecosystem}:{normalise(self.name)}@{self.version}"


class Finding(BaseModel):
    """One known vulnerability in one library version, and every source that reported it."""

    id: str
    aliases: list[str] = Field(default_factory=list)
    package: str
    ecosystem: Ecosystem
    version: str
    summary: str = ""
    severity: str = "unknown"  # low | moderate | high | critical | unknown
    fixed_in: list[str] = Field(default_factory=list)
    link: str = ""
    found_by: list[str] = Field(default_factory=list)

    def names(self) -> set[str]:
        return {self.id, *self.aliases}


class SourceStatus(BaseModel):
    name: str
    status: Literal["ok", "unavailable", "not_installed", "skipped"]
    detail: str = ""
    checked: int = 0  # how many libraries the source looked at
    found: int = 0  # how many vulnerabilities it reported


class CheckResult(BaseModel):
    checked_at: str
    dependencies: list[Dependency]
    findings: list[Finding]
    sources: list[SourceStatus]
    unchecked: int = 0  # libraries without a known version
