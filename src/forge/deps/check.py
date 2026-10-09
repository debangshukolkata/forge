"""Runs both vulnerability sources and merges what they found, so each vulnerability says which
source(s) reported it (D-238)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from forge.deps import audit, licenses, osv
from forge.deps.model import CheckResult, Dependency, Finding, SourceStatus, normalise

SEVERITY_ORDER = ["critical", "high", "moderate", "low", "unknown"]


def merge(batches: list[list[Finding]]) -> list[Finding]:
    """The same vulnerability under different ids (a GHSA id in one source, a PYSEC or CVE id in the other)
    is one finding, found by both. Two findings are the same when they share the library, its version
    and any id."""
    merged: list[Finding] = []
    for batch in batches:
        for finding in batch:
            same = next(
                (
                    m
                    for m in merged
                    if normalise(m.package) == normalise(finding.package)
                    and m.version == finding.version
                    and m.names() & finding.names()
                ),
                None,
            )
            if same is None:
                merged.append(finding.model_copy(deep=True))
                continue
            same.aliases = sorted((same.names() | finding.names()) - {same.id})
            same.found_by = list(dict.fromkeys([*same.found_by, *finding.found_by]))
            same.fixed_in = list(dict.fromkeys([*same.fixed_in, *finding.fixed_in]))
            if same.severity == "unknown":
                same.severity = finding.severity
            same.summary = same.summary or finding.summary
    return sorted(merged, key=lambda f: (SEVERITY_ORDER.index(f.severity), normalise(f.package), f.id))


def run_check(
    dependencies: list[Dependency],
    osv_check: osv.ClientFactory | None = None,
    audit_runner: audit.Runner | None = None,
    license_client: licenses.ClientFactory | None = None,
) -> CheckResult:
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(osv.check, dependencies, osv_check)
        second = pool.submit(audit.check, dependencies, audit_runner)
        third = pool.submit(licenses.fill_licenses, dependencies, license_client)
        osv_findings, osv_status = first.result()
        audit_findings, audit_status = second.result()
        license_status = third.result()
    sources: list[SourceStatus] = [osv_status, audit_status, license_status]
    return CheckResult(
        checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
        dependencies=dependencies,
        findings=merge([osv_findings, audit_findings]),
        sources=sources,
        unchecked=sum(1 for d in dependencies if not d.version),
    )
