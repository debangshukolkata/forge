"""Client of the deployment system's API. In this repository the system is simulated in process."""

from __future__ import annotations

import json

TEAMS = ("payments", "search", "identity", "catalog", "orders", "shipping", "pricing", "reports")
STAGES = ("api", "worker", "web", "cron", "gateway")


def _application(index: int) -> dict[str, object]:
    name = f"{TEAMS[index % len(TEAMS)]}-{STAGES[index % len(STAGES)]}-{index:03d}"
    return {
        "metadata": {
            "name": name,
            "namespace": "argocd",
            "labels": {"team": TEAMS[index % len(TEAMS)], "tier": STAGES[index % len(STAGES)]},
            "annotations": {f"notes.example.com/line-{n}": "x" * 120 for n in range(6)},
        },
        "spec": {
            "source": {"repoURL": f"https://git.example.com/{name}.git", "path": "deploy", "targetRevision": "main"},
            "destination": {"server": "https://kubernetes.default.svc", "namespace": name},
            "syncPolicy": {"automated": {"prune": True, "selfHeal": True}},
        },
        "status": {
            "sync": {"status": "Synced", "revision": f"{index:040x}"},
            "health": {"status": "Healthy"},
            "resources": [
                {"kind": kind, "name": f"{name}-{kind.lower()}", "status": "Synced", "health": "Healthy"}
                for kind in ("Deployment", "Service", "ConfigMap", "Ingress", "HorizontalPodAutoscaler")
            ],
            "history": [{"id": n, "revision": f"{index + n:040x}", "deployedAt": "2026-01-01T00:00:00Z"} for n in range(8)],
        },
    }


def call(path: str) -> str:
    """The body the deployment API returns for a GET of `path`, as text."""
    if path == "/api/v1/applications":
        return json.dumps({"items": [_application(index) for index in range(120)]})
    if path == "/api/v1/version":
        return json.dumps({"Version": "v2.9.3", "Platform": "linux/amd64"})
    if path == "/api/v1/invoices":
        return json.dumps({"items": [{"number": f"INV-{n:04d}", "amount": 100 + n} for n in range(12)]})
    raise LookupError(f"no such API path: {path}")
