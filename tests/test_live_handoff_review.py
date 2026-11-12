"""Live (the real reviewer model): does the hand-off review tell a needless card from a needed one (D-571)?

Eight cards nobody wrote a pattern for: four that DebCraft can do itself (they must be sent back, at least
three of four) and four that only the user can do (all four must be shown: hiding a needed card is the worse
mistake). Set HANDOFF_REVIEW_LOG to a file to get one JSON line per card."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.llm.router import LLMRouter
from forge.toolkit.base import ToolContext
from forge.tools.handoff_review import review_hand_off
from forge.tools.registry import ToolRegistry
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live

# (the user's last message, title, steps, DebCraft can do it itself)
CARDS: list[tuple[str, str, list[str], bool]] = [
    (
        "start the backend please",
        "Confirm the database port",
        ["Open backend/claims_app/config.py and tell me which port the database URL uses."],
        True,
    ),
    (
        "run the tests",
        "Install the test runner",
        [
            "Open PowerShell in the project folder.",
            "Run `pip install pytest` in the project's virtual environment.",
        ],
        True,
    ),
    (
        "the infisical values are in my .env file, I told you already",
        "Copy the Infisical settings into the repository",
        [
            "Copy INFISICAL_CLIENT_ID and INFISICAL_CLIENT_SECRET from your DebCraft .env file into backend/.env."
        ],
        True,
    ),
    (
        "why does the endpoint return 500?",
        "Send me the server log",
        ["Run the application, call POST /claims once and paste the last 50 lines of its output here."],
        True,
    ),
    (
        "list the deployments through ArgoCD",
        "Create an ArgoCD API token",
        [
            "Log in to the ArgoCD console of your company, open Settings > Accounts and generate a token.",
            "Add it to your app.env file as ARGOCD_TOKEN and answer here.",
        ],
        False,
    ),
    (
        "read the claims tables from the development database",
        "Grant read access on the claims schema",
        [
            "Ask your database administrator to run: GRANT SELECT ON ALL TABLES IN SCHEMA claims TO forge_reader;"
        ],
        False,
    ),
    (
        "build the container image",
        "Install Docker Desktop",
        [
            "Install Docker Desktop from the company software portal (it needs administrator rights) and start it."
        ],
        False,
    ),
    (
        "call the staging gateway",
        "Connect to the company VPN",
        [
            "Connect this laptop to the company VPN so that the staging gateway can be reached, then answer here."
        ],
        False,
    ),
]


async def test_the_review_sends_back_needless_cards_and_shows_needed_ones(
    tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(
        (REPO_ROOT / ".env").read_text(encoding="utf-8")
        + "\nINFISICAL_CLIENT_ID=client-12345678\nINFISICAL_CLIENT_SECRET=secret-12345678\n",  # check_secrets: fake
        encoding="utf-8",
    )
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    workspace = create_workspace(REPO_ROOT / "tests" / "fixtures" / "sample_repo", tmp_path / "ws", "backend")
    router = LLMRouter(load_config(isolated_forge_home), secrets)
    registry = ToolRegistry()
    catalog = [
        f"{name}: {tool.description.split('. ')[0][:220]}"
        for name in registry.names()
        if (tool := registry.get(name)) is not None
    ]
    rows = []
    for said, title, steps, own_job in CARDS:
        context = ToolContext(workspace=workspace)
        context.router = router
        context.tool_catalog = lambda: catalog
        context.recent_user_messages = lambda said=said: [said]  # type: ignore[misc]
        sent_back = await review_hand_off(title, steps, None, context)
        rows.append(
            {
                "title": title,
                "own_job": own_job,
                "sent_back": sent_back is not None,
                "model": router.model_for_role("reviewer"),
                "told": (sent_back or "")[:500],
            }
        )
    log = os.environ.get("HANDOFF_REVIEW_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.writelines(json.dumps(row) + "\n" for row in rows)
    print(
        "\n"
        + "\n".join(f"{row['own_job']!s:5} sent back={row['sent_back']!s:5} {row['title']}" for row in rows)
    )
    hidden = [row["title"] for row in rows if not row["own_job"] and row["sent_back"]]
    caught = [row["title"] for row in rows if row["own_job"] and row["sent_back"]]
    assert not hidden, f"needed cards were held back: {hidden}"
    assert len(caught) >= 3, f"needless cards were shown: only {caught} were sent back"
