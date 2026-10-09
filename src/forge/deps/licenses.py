"""License source 2: deps.dev, Google's open package database (D-239). It fills in the libraries whose
license could not be read from an installed copy. Only library names and versions are sent, and only when
the user asks for the check (the same click as the vulnerability check). When deps.dev lists several
licenses for one version they are joined with AND, the cautious reading of "which one applies"."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import httpx

from forge.deps.model import SOURCE_DEPS_DEV, Dependency, SourceStatus

API = "https://api.deps.dev/v3/systems"
SYSTEMS = {"PyPI": "pypi", "npm": "npm"}
MAX_LOOKUPS = 600
TIMEOUT_S = 20.0
ClientFactory = Callable[[], httpx.Client]


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S)


def fill_licenses(
    dependencies: list[Dependency], client_factory: ClientFactory | None = None
) -> SourceStatus:
    """Sets `license` on every library that has a version but no license yet. Never raises."""
    missing = [d for d in dependencies if d.version and not d.license][:MAX_LOOKUPS]
    if not missing:
        return SourceStatus(name=SOURCE_DEPS_DEV, status="skipped", detail="Every license was already known.")

    def lookup(client: httpx.Client, dependency: Dependency) -> str | None:
        system, name, version = SYSTEMS[dependency.ecosystem], dependency.name, str(dependency.version)
        response = client.get(
            f"{API}/{system}/packages/{quote(name, safe='')}/versions/{quote(version, safe='')}"
        )
        if response.status_code == 404:
            return ""  # deps.dev does not know this version: not a failure of the service
        response.raise_for_status()
        names = [str(n) for n in response.json().get("licenses", []) if str(n).lower() != "non-standard"]
        return " AND ".join(names) if names else ""

    try:
        with (client_factory or _client)() as client, ThreadPoolExecutor(max_workers=8) as pool:
            for dependency, found in zip(
                missing, pool.map(lambda d: lookup(client, d), missing), strict=True
            ):
                if found:
                    dependency.license, dependency.license_source = found, SOURCE_DEPS_DEV
    except (httpx.HTTPError, ValueError, KeyError) as error:
        detail = f"Could not reach deps.dev ({type(error).__name__}). Check the network or proxy."
        return SourceStatus(name=SOURCE_DEPS_DEV, status="unavailable", detail=detail)
    filled = sum(1 for d in missing if d.license_source == SOURCE_DEPS_DEV)
    return SourceStatus(
        name=SOURCE_DEPS_DEV, status="ok", detail="licenses", checked=len(missing), found=filled
    )
