"""D-410: risks in the code the model worked with are found and named once before the turn ends."""

from __future__ import annotations

from pathlib import Path

import httpx2

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.safety.risk_scan import mentioned, scan_text, scannable
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router, reply, responses_body, text_output

SETTINGS = '''"""Application settings."""
import pickle

API_TOKEN = "tok_live_8f3a91c2d7e44b6f9a0c"


def load_settings(path):
    with open(path, "rb") as handle:
        return pickle.loads(handle.read())
'''

SQL = """def get_user(connection, name):
    query = f"SELECT id FROM users WHERE name = '{name}'"
    return connection.execute(query).fetchone()
"""


def test_the_usual_suspects_are_found_with_their_line() -> None:
    kinds = {risk.kind: risk.line for risk in scan_text("settings.py", SETTINGS)}
    assert kinds == {"hard-coded secret": 4, "unsafe deserialisation": 9}
    assert [r.kind for r in scan_text("users.py", SQL)] == ["SQL built from strings"]


def test_placeholders_comments_and_safe_code_are_not_findings() -> None:
    assert (
        scan_text(
            "a.py", 'API_KEY = "your-key-here-please"\n# pickle.loads(x)\nvalue = yaml.safe_load(text)\n'
        )
        == []
    )
    assert scan_text("a.py", 'connection.execute("SELECT id FROM users WHERE name = ?", (name,))\n') == []
    assert scan_text("a.py", 'PASSWORD = "<set me>"\n') == []


def test_tests_and_non_source_files_are_not_scanned() -> None:
    assert (
        scannable("shop/orders.py") and not scannable("tests/test_orders.py") and not scannable("README.md")
    )
    assert not scannable("web/src/app.test.tsx") and not scannable("conftest.py")


def test_a_reply_that_names_the_risk_is_left_alone() -> None:
    risk = scan_text("settings.py", SETTINGS)[1]
    assert not mentioned(risk, "Done. I added get_timeout and tests.")
    assert mentioned(
        risk, "Noticed, not changed: settings.py:9 loads the file with pickle, which can run code."
    )


async def test_the_loop_asks_once_for_unreported_risks_when_it_changed_something(
    original_repo: Path, tmp_path: Path
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return reply(request, responses_body([text_output("ok")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("settings.py", SETTINGS, "seed")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    loop = host.agent
    assert loop is not None
    loop.context.reads.record("settings.py", SETTINGS.encode())
    assert (
        loop._unreported_risks("Done.") == []
    )  # nothing was changed in this session: no nagging on a pure read
    loop.context.last_edit_step = 3
    found = loop._unreported_risks("Done.")
    assert len(found) == 2 and any("pickle" in line or "deserialisation" in line for line in found)
    assert (
        loop._unreported_risks("Noticed: settings.py pickle load can run code; the token is hard-coded.")
        == []
    )
