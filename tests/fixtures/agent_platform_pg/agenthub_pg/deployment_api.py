"""Client of the deployment system's API. The applications are rows of the `applications` table (the deployment
system's state lives in the database); the version and the invoices are simulated in process."""

from __future__ import annotations

import json


def call(path: str) -> str:
    """The body the deployment API returns for a GET of `path`, as text."""
    if path == "/api/v1/applications":
        from agenthub_pg import store

        return json.dumps({"items": store.applications()})
    if path == "/api/v1/version":
        return json.dumps({"Version": "v2.9.3", "Platform": "linux/amd64"})
    if path == "/api/v1/invoices":
        return json.dumps({"items": [{"number": f"INV-{n:04d}", "amount": 100 + n} for n in range(12)]})
    raise LookupError(f"no such API path: {path}")
