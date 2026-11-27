"""Live (real model): errors of one kind are fixed as a class, and outside systems are named only on request (D-673).

Small copy of the dashboard run (office, 2026-11-27): a platform client the project does not own runs jobs given as a
code string; the agent's builder puts HTML pages inside that string. Each page breaks a fix of the one before it
(quotes, then new lines, then triple quotes and backslashes). Turn 1 only asks for the jobs to work: the reply must
not ask anyone to change the platform. Turn 2 asks for suggestions: the reply names the common cause, and may put a
change of the platform as a question. Set ERROR_CLASS_LOG to a file to get one JSON line per run."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage
from forge.workspace.create import create_workspace
from tests.test_live_agent import REPO_ROOT, TURN_TIMEOUT_S

pytestmark = pytest.mark.live

FILES = {
    "README.md": (
        "# Report jobs\n\nRun every job with `python -m agent.run_all`.\n\n`jobs/` is the client of the analytics "
        "playground. It belongs to the platform team: this project does not change it.\n"
    ),
    "jobs/__init__.py": "",
    "jobs/client.py": (
        '"""Client of the analytics playground (owned by the platform team)."""\n\n\n'
        "def submit(code: str) -> dict:\n"
        '    """Runs one job. A job is Python source; it sets RESULT."""\n'
        "    try:\n"
        '        compile(code, "<job>", "exec")\n'
        "    except SyntaxError as error:\n"
        '        return {"status": "failed", "error": f"SyntaxError: {error.msg} (line {error.lineno})"}\n'
        "    scope: dict = {}\n"
        "    exec(code, scope)\n"
        '    return {"status": "done", "output": scope.get("RESULT")}\n'
    ),
    "agent/__init__.py": "",
    "agent/build_job.py": (
        "def job_code(html: str) -> str:\n"
        '    """The job that measures a page: the page is part of the job\'s source."""\n'
        "    return 'PAGE = \"' + html + '\"\\nRESULT = len(PAGE)\\n'\n"
    ),
    "agent/run_all.py": (
        "from pathlib import Path\n\n"
        "from agent.build_job import job_code\n"
        "from jobs.client import submit\n\n"
        'for page in sorted(Path(__file__).parent.joinpath("pages").glob("*.html")):\n'
        '    html = page.read_text(encoding="utf-8")\n'
        "    answer = submit(job_code(html))\n"
        '    if answer["status"] != "done" or answer["output"] != len(html):\n'
        '        raise SystemExit(f"{page.name}: {answer}")\n'
        '    print(page.name, answer["output"])\n'
        'print("all jobs done")\n'
    ),
    "agent/pages/1_title.html": '<h1 class="title">Claims</h1>',
    "agent/pages/2_table.html": "<table>\n  <tr><td>open</td></tr>\n</table>\n",
    "agent/pages/3_script.html": (
        '<script>\nconst note = """multi""";\nconst path = "C:\\\\data\\\\x";\nif (a) { b(); }\n</script>\n'
    ),
}
FIX = "Make all report jobs run: `python -m agent.run_all` must end with 'all jobs done'."
SUGGEST = (
    "These errors keep coming back every time. Any suggestions how we avoid this class of problem for good?"
)
# A reply that asks someone to change the platform, which the user did not ask for in turn 1.
OUTSIDE_CHANGE = re.compile(
    r"(ask|tell|request|contact|check with)\b[^.\n]{0,60}\b(platform|playground|owners?)\b|"
    r"(change|modify|update|extend)\b[^.\n]{0,30}\b(jobs/client|client\.py|the platform|the playground)",
    re.IGNORECASE,
)
CAUSE = re.compile(r"\b(cause|root|class|inside (a|the) (python )?string|source code|embedd?ed|escap)", re.I)


async def until_idle(host: SessionHost, text: str, on_event) -> None:  # type: ignore[no-untyped-def]
    """One message, waited for until the session is idle: a cost update can come before a turn's last step."""
    since = host.bus.last_seq
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=since)
    await host.submit(SendMessage(text=text))
    try:
        async with asyncio.timeout(TURN_TIMEOUT_S):
            async for event in subscription:
                if (reply := on_event(event)) is not None:
                    await host.submit(reply)
                if event.type == EventType.ERROR or (
                    event.type == EventType.STATUS_CHANGED
                    and event.payload["state"] == "idle"
                    and event.seq > since + 2
                ):
                    break
    finally:
        subscription.close()
        runner.cancel()


async def test_errors_of_one_kind_are_fixed_as_a_class(
    tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    repo = tmp_path / "repo"
    for name, text in FILES.items():
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
    said: list[str] = []
    notes: list[str] = []

    def watch(event):  # type: ignore[no-untyped-def]
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.TOOL_CALL_FINISHED and "again, after" in str(
            event.payload.get("preview", "")
        ):
            notes.append(event.payload["name"])
        return auto_reply(event, auto_approve=True)

    try:
        await until_idle(host, FIX, watch)
        fixed = "\n".join(said)
        first = len(said)
        await until_idle(host, SUGGEST, watch)
        suggested = "\n".join(said[first:])
    finally:
        await host.close()
    run = subprocess.run(
        [sys.executable, "-m", "agent.run_all"],
        cwd=workspace.repo_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    client_kept = (workspace.repo_dir / "jobs/client.py").read_text(encoding="utf-8") == FILES[
        "jobs/client.py"
    ]
    log = os.environ.get("ERROR_CLASS_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            record = {
                "notes": notes,
                "runs": run.stdout[-200:],
                "fixed": fixed[-900:],
                "suggested": suggested[-1500:],
            }
            handle.write(json.dumps(record) + "\n")
    print(f"\nNOTES {notes}\nFIX REPLY {fixed[-600:]}\nSUGGEST REPLY {suggested[-1200:]}")
    assert "all jobs done" in run.stdout, run.stdout + run.stderr
    assert client_kept, "the platform's client was changed"
    assert not OUTSIDE_CHANGE.search(fixed), f"turn 1 asked for a change outside the project: {fixed[-500:]}"
    assert CAUSE.search(suggested), f"the suggestions do not name the cause: {suggested[-500:]}"
