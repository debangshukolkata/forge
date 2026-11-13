"""The rows of the `applications` table of a real deployment system, generated for tests. The application never
imports this; a test (or a person) fills a database with it, as the user's development database would be filled."""

from __future__ import annotations

TEAMS = ("payments", "search", "identity", "catalog", "orders", "shipping", "pricing", "reports")
STAGES = ("api", "worker", "web", "cron", "gateway")


def application(index: int) -> dict[str, object]:
    name = f"{TEAMS[index % len(TEAMS)]}-{STAGES[index % len(STAGES)]}-{index:03d}"
    return {
        "metadata": {
            "name": name,
            "namespace": "argocd",
            "labels": {"team": TEAMS[index % len(TEAMS)], "tier": STAGES[index % len(STAGES)]},
            "annotations": {f"notes.example.com/line-{n}": "x" * 120 for n in range(6)},
        },
        "spec": {
            "source": {
                "repoURL": f"https://git.example.com/{name}.git",
                "path": "deploy",
                "targetRevision": "main",
            },
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
            "history": [
                {"id": n, "revision": f"{index + n:040x}", "deployedAt": "2026-01-01T00:00:00Z"}
                for n in range(8)
            ],
        },
    }


def rows(count: int = 120) -> list[tuple[str, str]]:
    """(name, document as JSON text) for each application."""
    import json

    return [(str(item["metadata"]["name"]), json.dumps(item)) for item in map(application, range(count))]  # type: ignore[index]
