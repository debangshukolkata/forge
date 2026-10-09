"""Vulnerability source 1: OSV.dev, the open database of known vulnerabilities (D-238). Only library names and
versions are sent, and only when the user asks for the check."""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from forge.deps.model import SOURCE_OSV, Dependency, Finding, SourceStatus, normalise

_COMMIT = re.compile(r"[0-9a-f]{40}")  # OSV also lists the fixing commit; a version is what the user needs
API = "https://api.osv.dev/v1"
BATCH = 500
MAX_DETAILS = 300  # vulnerability records fetched per check
TIMEOUT_S = 30.0
SEVERITIES = {
    "LOW": "low",
    "MODERATE": "moderate",
    "MEDIUM": "moderate",
    "HIGH": "high",
    "CRITICAL": "critical",
}
ClientFactory = Callable[[], httpx.Client]


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S)


def _fixed_versions(record: dict[str, Any], dependency: Dependency) -> list[str]:
    fixed: list[str] = []
    for affected in record.get("affected", []):
        package = affected.get("package", {})
        if normalise(str(package.get("name", ""))) != normalise(dependency.name):
            continue
        for item in affected.get("ranges", []):
            fixed += [str(event["fixed"]) for event in item.get("events", []) if "fixed" in event]
    return [v for v in dict.fromkeys(fixed) if not _COMMIT.fullmatch(v)]


def _severity(record: dict[str, Any]) -> str:
    label = str((record.get("database_specific") or {}).get("severity", "")).upper()
    return SEVERITIES.get(label, "unknown")


def _link(record: dict[str, Any]) -> str:
    return f"https://osv.dev/vulnerability/{record['id']}"


def _finding(record: dict[str, Any], dependency: Dependency) -> Finding:
    return Finding(
        id=str(record["id"]),
        aliases=[str(alias) for alias in record.get("aliases", [])],
        package=dependency.name,
        ecosystem=dependency.ecosystem,
        version=str(dependency.version),
        summary=str(record.get("summary") or str(record.get("details", ""))[:200]),
        severity=_severity(record),
        fixed_in=_fixed_versions(record, dependency),
        link=_link(record),
        found_by=[SOURCE_OSV],
    )


def check(
    dependencies: list[Dependency], client_factory: ClientFactory | None = None
) -> tuple[list[Finding], SourceStatus]:
    """Asks OSV about every library with a known version. Never raises: a failure becomes the status."""
    known = [d for d in dependencies if d.version]
    status = SourceStatus(name=SOURCE_OSV, status="ok", checked=len(known))
    if not known:
        return [], SourceStatus(name=SOURCE_OSV, status="skipped", detail="No library has a known version.")
    try:
        with (client_factory or _client)() as client:
            hits = _query_all(client, known)
            records = _records(client, {vuln_id for ids in hits.values() for vuln_id in ids})
    except (httpx.HTTPError, ValueError, KeyError) as error:
        detail = f"Could not reach osv.dev ({type(error).__name__}). Check the network or proxy."
        return [], SourceStatus(name=SOURCE_OSV, status="unavailable", detail=detail)
    findings = [
        _finding(records[vuln_id], dependency)
        for index, ids in hits.items()
        for dependency in [known[index]]
        for vuln_id in ids
        if vuln_id in records
    ]
    status.found = len(findings)
    if len({v for ids in hits.values() for v in ids}) > MAX_DETAILS:
        status.detail = f"Details were fetched for the first {MAX_DETAILS} vulnerabilities only."
    return findings, status


def _query_all(client: httpx.Client, known: list[Dependency]) -> dict[int, list[str]]:
    hits: dict[int, list[str]] = {}
    for start in range(0, len(known), BATCH):
        chunk = known[start : start + BATCH]
        body = {
            "queries": [
                {"package": {"name": d.name, "ecosystem": d.ecosystem}, "version": d.version} for d in chunk
            ]
        }
        response = client.post(f"{API}/querybatch", json=body)
        response.raise_for_status()
        for offset, result in enumerate(response.json()["results"]):
            ids = [str(v["id"]) for v in result.get("vulns", [])]
            if ids:
                hits[start + offset] = ids
    return hits


def _records(client: httpx.Client, ids: set[str]) -> dict[str, dict[str, Any]]:
    wanted = sorted(ids)[:MAX_DETAILS]

    def fetch(vuln_id: str) -> tuple[str, dict[str, Any] | None]:
        response = client.get(f"{API}/vulns/{vuln_id}")
        return (vuln_id, response.json()) if response.status_code == 200 else (vuln_id, None)

    with ThreadPoolExecutor(max_workers=8) as pool:
        return {vuln_id: record for vuln_id, record in pool.map(fetch, wanted) if record is not None}
