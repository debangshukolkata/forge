"""D-129: the Contracts panel's endpoints (Mode B): list, pin, revise, forget. No model calls."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from forge.modeb.profile import ProfileStore
from forge.safety.server_security import ServerSecurity
from tests.test_web import ORIGIN, client, login, security  # noqa: F401  (fixtures are used by name)

SIGNATURE = "def call_llm(prompt: str, **kwargs) -> LLMResponse"


def test_no_project_means_no_contracts(client: TestClient, security: ServerSecurity) -> None:  # noqa: F811
    login(client, security)
    assert client.get("/api/contracts").json() == {"available": False, "contracts": []}
    pinned = client.post("/api/contracts", json={"seam": "x", "signature": "def x()"}, headers=ORIGIN)
    assert pinned.status_code == 400


def test_pin_revise_and_forget(
    client: TestClient,  # noqa: F811
    security: ServerSecurity,  # noqa: F811
    isolated_forge_home: Path,
    tmp_path: Path,
) -> None:
    login(client, security)
    ProfileStore(isolated_forge_home).create("web-host")
    client.post("/api/standalone", json={"workspace": str(tmp_path / "wsb"), "profile": "web-host"})
    assert client.get("/api/contracts").json() == {"available": True, "contracts": []}

    body = {"seam": "llm_call_wrapper", "signature": SIGNATURE, "note": "used everywhere"}
    pinned = client.post("/api/contracts", json=body, headers=ORIGIN)
    assert pinned.status_code == 200, pinned.text
    [contract] = pinned.json()["contracts"]
    assert contract["seam"] == "llm_call_wrapper" and contract["signature"] == SIGNATURE
    assert contract["note"] == "used everywhere" and contract["revised"] == ""

    # Pinning the same seam again is a revision, not a second contract.
    revised = client.post("/api/contracts", json={**body, "signature": SIGNATURE + " | None"}, headers=ORIGIN)
    [only] = revised.json()["contracts"]
    assert only["id"] == contract["id"] and only["revised"] and only["signature"].endswith("| None")

    bad = client.post("/api/contracts", json={"seam": "Not A Seam", "signature": "def x()"}, headers=ORIGIN)
    assert bad.status_code == 400 and "lowercase" in bad.json()["detail"]
    empty = client.post("/api/contracts", json={"seam": "x", "signature": ""}, headers=ORIGIN)
    assert empty.status_code == 422

    assert client.delete("/api/contracts/llm_call_wrapper", headers=ORIGIN).json()["contracts"] == []
    assert client.delete("/api/contracts/llm_call_wrapper", headers=ORIGIN).status_code == 404
