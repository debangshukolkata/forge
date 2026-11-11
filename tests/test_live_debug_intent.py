"""Live (real Azure model): when a run fails, DebCraft finds the exact cause itself instead of guessing (D-567).

The user's report: a copied repository failed to start because entries were missing from its env file, and
DebCraft guessed at the reason until told to go and check. Each scenario is a small app whose start fails for
a missing setting; the request is only "run it". A run passes when the answer names the exact missing setting
(found by reading the code and the env file's keys), not a general "check your configuration".
Set DEBUG_INTENT_LOG to a file to get one JSON line per run."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.workspace.create import create_workspace
from tests.test_live_agent import REPO_ROOT, run_turn

pytestmark = pytest.mark.live

# The error names nothing: the model has to open settings.py and compare it with the env file's keys.
VAGUE = {
    "service/__init__.py": "",
    "service/settings.py": (
        "import os\n\n"
        'QUEUE_HOST = os.getenv("QUEUE_HOST")\n'
        'QUEUE_TOKEN = os.getenv("QUEUE_TOKEN")\n'
        'REPORT_BUCKET = os.getenv("REPORT_BUCKET")\n\n\n'
        "def check() -> None:\n"
        "    if not all([QUEUE_HOST, QUEUE_TOKEN, REPORT_BUCKET]):\n"
        '        raise RuntimeError("configuration incomplete")\n'
    ),
    "service/main.py": (
        "from pathlib import Path\n\n"
        "for line in Path(__file__).resolve().parent.parent.joinpath('.env').read_text().splitlines():\n"
        "    if '=' in line and not line.startswith('#'):\n"
        "        import os\n"
        "        key, _, value = line.partition('=')\n"
        "        os.environ.setdefault(key.strip(), value.strip())\n\n"
        "from service import settings\n\n\n"
        "def main() -> None:\n"
        "    settings.check()\n"
        '    print("service ready")\n\n\n'
        'if __name__ == "__main__":\n'
        "    main()\n"
    ),
    ".env": "QUEUE_HOST=queue.internal\nLOG_LEVEL=info\n",
    "README.md": "# Service\n\nStart it with `python -m service.main`.\n",
}
# The error is a TypeError two calls away from the setting.
INDIRECT = {
    "worker/__init__.py": "",
    "worker/config.py": (
        "import os\n\n\n"
        "def pool_size() -> int:\n"
        '    return int(os.getenv("WORKER_POOL_SIZE"))\n\n\n'
        "def region() -> str:\n"
        '    return os.getenv("WORKER_REGION", "eu")\n'
    ),
    "worker/main.py": (
        "from worker.config import pool_size, region\n\n\n"
        "def start() -> list[int]:\n"
        "    return list(range(pool_size()))\n\n\n"
        'if __name__ == "__main__":\n'
        '    print("workers", len(start()), region())\n'
    ),
    ".env": "WORKER_REGION=us\n",
    "README.md": "# Worker\n\nStart it with `python -m worker.main`.\n",
}
# A module deep in a larger repository; the user only reports the error, the way a failure usually arrives.
MAILER = {
    "backend/claims_app/notifications/__init__.py": "",
    "backend/claims_app/notifications/relay.py": (
        "import os\n\n\n"
        "class RelaySettings:\n"
        "    def __init__(self) -> None:\n"
        '        self.host = os.getenv("SMTP_RELAY_HOST")\n'
        '        self.key = os.getenv("SMTP_RELAY_KEY")\n'
        '        self.sender = os.getenv("SMTP_SENDER", "claims@example.com")\n\n'
        "    def ready(self) -> bool:\n"
        "        return bool(self.host and self.key)\n"
    ),
    "backend/claims_app/notifications/mailer.py": (
        "from claims_app.notifications.relay import RelaySettings\n\n\n"
        "def send_nightly_digest() -> int:\n"
        "    settings = RelaySettings()\n"
        "    if not settings.ready():\n"
        '        raise RuntimeError("mailer is not configured")\n'
        "    return 0\n"
    ),
}
RUN = "Run this app and tell me whether it works."
SCENARIOS: dict[str, tuple[dict[str, str], str, list[str], str]] = {
    "vague": (VAGUE, RUN, ["QUEUE_TOKEN", "REPORT_BUCKET"], ""),
    "indirect": (INDIRECT, RUN, ["WORKER_POOL_SIZE"], ""),
    "reported": (
        VAGUE,
        "I started the service and it fails with `RuntimeError: configuration incomplete`. What is wrong?",
        ["QUEUE_TOKEN", "REPORT_BUCKET"],
        "",
    ),
    "reported_big": (
        MAILER,
        "The nightly digest job fails with `RuntimeError: mailer is not configured`. What is wrong?",
        ["SMTP_RELAY_KEY"],
        "SMTP_RELAY_HOST=relay.internal\n",  # appended to the fixture's backend/.env: the host is there, the key is not
    ),
}


@pytest.mark.parametrize("scenario", list(SCENARIOS))
async def test_a_failed_start_is_traced_to_the_exact_missing_setting(
    scenario: str, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    files, request, expected, env_lines = SCENARIOS[scenario]
    repo = tmp_path / "repo"
    if env_lines:  # the larger fixture repository, with this scenario's files added to it
        shutil.copytree(
            REPO_ROOT / "tests" / "fixtures" / "sample_repo",
            repo,
            ignore=shutil.ignore_patterns("venv", "__pycache__", ".pytest_cache", "node_modules"),
        )
        with open(repo / "backend" / ".env", "a", encoding="utf-8") as handle:
            handle.write("\n" + env_lines)
    for name, text in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    workspace = create_workspace(repo, tmp_path / "ws", "")
    host = SessionHost(
        LLMRouter(load_config(isolated_forge_home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
    )
    calls: list[str] = []
    said: list[str] = []
    handed: list[str] = []

    def watch(event):  # type: ignore[no-untyped-def]
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:110])
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.USER_ACTION_REQUESTED:
            handed.append(json.dumps(event.payload)[:600])
        return auto_reply(event, auto_approve=True)

    try:
        await run_turn(host, request, watch)
    finally:
        await host.close()
    answer = "\n".join([*said, *handed])
    missing = [name for name in expected if name not in answer]
    log = os.environ.get("DEBUG_INTENT_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"scenario": scenario, "calls": calls, "not_named": missing, "answer": answer[-900:]}
                )
                + "\n"
            )
    print(f"\nSCENARIO {scenario}: {len(calls)} calls; not named: {missing}; calls={calls}")
    assert not missing, f"the answer does not name {missing}: {answer[-500:]}"
