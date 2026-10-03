"""D-195: the endpoint that serves a saved tool output. No model calls."""

from __future__ import annotations

from fastapi.testclient import TestClient

from forge.agent.tool_output import FOLDER
from forge.safety.server_security import ServerSecurity
from forge.workspace.workspace import Workspace
from tests.test_web import client, login, security, workspace  # noqa: F401  (fixtures are used by name)

OUTPUT_ID = "0123456789abcdef0123456789abcdef"


def test_no_project_open(client: TestClient, security: ServerSecurity) -> None:  # noqa: F811
    login(client, security)
    assert client.get(f"/api/tool-output/{OUTPUT_ID}").status_code == 400


def test_serves_a_saved_output(
    client: TestClient,  # noqa: F811
    security: ServerSecurity,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    login(client, security)
    client.post(
        "/api/open",
        json={"workspace": str(workspace.root)},
        headers={"origin": f"http://127.0.0.1:{security.port}"},
    )
    folder = workspace.forge_dir / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{OUTPUT_ID}.txt").write_text("the whole result\nline two", encoding="utf-8")

    found = client.get(f"/api/tool-output/{OUTPUT_ID}")
    assert found.status_code == 200 and found.json() == {"text": "the whole result\nline two", "chars": 25}
    assert client.get("/api/tool-output/ffffffffffffffffffffffffffffffff").status_code == 404  # not saved
    for bad in ("..%2F..%2Fworkspace.json", "not-an-id", "A" * 32):
        assert client.get(f"/api/tool-output/{bad}").status_code == 404
