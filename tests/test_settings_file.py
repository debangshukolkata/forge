"""`settings_file`: the user's own yaml files are written only with their approval, checked first (D-618)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from forge.toolkit.app_logins import load_logins
from forge.toolkit.base import ToolContext
from forge.tools.settings_file import SettingsFile
from forge.workspace.create import create_workspace

LOGINS = """environments:
  dev:
    login_url: https://dev.example.com/app/login/
    token_name: DEV_TOKEN
    token: {cookie: access_token_cookie}
    steps:
      - click: "Sign in"
      - wait_url: "landing"
    check_url: https://dev.example.com/app/api/me
"""
TUNNELS = """tunnels:
  dev:
    command: [gcloud, compute, start-iap-tunnel, db1, "4572", --local-host-port=localhost:9006]
    port: 9006
"""


class Cards:
    """Stands in for the red card: records what the user was shown and answers as told."""

    def __init__(self, approve: bool = True, note: str = "") -> None:
        self.approve, self.note = approve, note
        self.shown: list[tuple[str, str, str]] = []

    async def __call__(self, question: str, details: str, label: str) -> tuple[bool, str]:
        self.shown.append((question, details, label))
        return self.approve, self.note


@pytest.fixture
def context(original_repo: Path, tmp_path: Path, isolated_forge_home: Path) -> ToolContext:
    return ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))


async def run(context: ToolContext, **fields: object):  # type: ignore[no-untyped-def]
    return await SettingsFile().run(SettingsFile.Args(**fields), context)  # type: ignore[arg-type]


async def test_a_file_is_written_only_after_the_user_approved_the_exact_text(
    context: ToolContext, isolated_forge_home: Path
) -> None:
    cards = Cards()
    context.confirm_danger = cards
    assert "does not exist" in (await run(context, action="read", file="app_logins.yaml")).content

    written = await run(
        context, action="write", file="app_logins.yaml", content=LOGINS, reason="sign in to dev"
    )
    assert written.ok, written.content
    assert (isolated_forge_home / "app_logins.yaml").read_text(encoding="utf-8") == LOGINS
    assert list(load_logins(isolated_forge_home)) == ["dev"]  # the real reader accepts what was written
    question, details, label = cards.shown[0]
    assert "Write app_logins.yaml" in question and label == "Write app_logins.yaml"
    assert LOGINS in details and "sign in to dev" in details and str(isolated_forge_home) in details
    assert not (isolated_forge_home / "app_logins.yaml.bak").exists()  # nothing to keep the first time
    assert (await run(context, action="read", file="app_logins.yaml")).content == LOGINS


async def test_a_change_shows_what_differs_and_keeps_the_previous_file(
    context: ToolContext, isolated_forge_home: Path
) -> None:
    (isolated_forge_home / "app_logins.yaml").write_text(LOGINS, encoding="utf-8")
    cards = Cards()
    context.confirm_danger = cards
    newer = LOGINS.replace("DEV_TOKEN", "DEVELOPMENT_INSTANCE_TOKEN")
    assert (await run(context, action="write", file="app_logins.yaml", content=newer, reason="rename")).ok
    details = cards.shown[0][1]
    assert (
        "-    token_name: DEV_TOKEN" in details and "+    token_name: DEVELOPMENT_INSTANCE_TOKEN" in details
    )
    assert (isolated_forge_home / "app_logins.yaml.bak").read_text(encoding="utf-8") == LOGINS
    assert (
        "already holds" in (await run(context, action="write", file="app_logins.yaml", content=newer)).content
    )


async def test_a_declined_card_changes_nothing(context: ToolContext, isolated_forge_home: Path) -> None:
    context.confirm_danger = Cards(approve=False, note="wrong host")
    refused = await run(context, action="write", file="tunnels.yaml", content=TUNNELS, reason="tunnel")
    assert not refused.ok and "did not approve" in refused.content and "wrong host" in refused.content
    assert not (isolated_forge_home / "tunnels.yaml").exists()


async def test_text_that_would_not_work_is_refused_before_the_user_is_asked(
    context: ToolContext, isolated_forge_home: Path
) -> None:
    cards = Cards()
    context.confirm_danger = cards
    wrong = "dev:\n  check_url: https://dev.example.com/me\n"  # the file found on the office laptop
    refused = await run(context, action="write", file="app_logins.yaml", content=wrong, reason="x")
    assert not refused.ok and "would not work" in refused.content and "`dev`" in refused.content
    bad_tunnel = await run(
        context, action="write", file="tunnels.yaml", content="tunnels:\n  dev: {port: 1}\n", reason="x"
    )
    assert not bad_tunnel.ok and "command" in bad_tunnel.content
    assert not cards.shown and not (isolated_forge_home / "app_logins.yaml").exists()


async def test_a_file_with_a_secret_in_it_is_refused(context: ToolContext, isolated_forge_home: Path) -> None:
    context.confirm_danger = Cards()
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzNDU2Nzg5MCJ9.c2lnbmF0dXJlc2lnbmF0dXJlc2lnbmF0dXJl"  # check_secrets: fake
    leaky = LOGINS + f"# token: {jwt}\n"
    refused = await run(context, action="write", file="app_logins.yaml", content=leaky, reason="x")
    assert not refused.ok and "secret" in refused.content
    assert not (isolated_forge_home / "app_logins.yaml").exists()


async def test_nobody_to_ask_or_a_host_project_means_no_write(
    context: ToolContext, isolated_forge_home: Path
) -> None:
    headless = await run(context, action="write", file="tunnels.yaml", content=TUNNELS, reason="x")
    assert not headless.ok and "cannot be asked" in headless.content
    assert not (isolated_forge_home / "tunnels.yaml").exists()
    nowhere = await SettingsFile().run(
        SettingsFile.Args(action="read", file="tunnels.yaml"), ToolContext(workspace=None)
    )
    assert not nowhere.ok


def test_only_the_two_user_files_can_be_named() -> None:
    with pytest.raises(ValidationError):
        SettingsFile.Args(action="write", file="config.yaml", content="x")  # type: ignore[arg-type]
