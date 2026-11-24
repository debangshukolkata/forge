"""Live (real Azure model): DebCraft builds question answering over a long recording (D-652, the video agent of 2026-11-24).

There it stored descriptions and answered by counting words, so a question about anything not described got an unrelated
sentence. The requirement here is worded as the user worded it. The test's own check starts the result with the real
model, indexes the recording and asks questions DebCraft never saw: covered by any summary, only seen for one moment,
reworded, and not in the recording at all.
Set RUNNING_SYSTEM_LOG to a file to get one JSON line per run, RUNNING_SYSTEM_KEEP to a folder to keep the run."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from dotenv import dotenv_values

from forge.config import load_config, load_secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage, UserInput
from forge.toolkit.app_keys import save_grant
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.test_agent_platform_pg import VENV_PYTHON, free_port

pytestmark = pytest.mark.live

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "recording_qa"
APP_VENV = VENV_PYTHON.parent.parent  # has the openai package
TURN_SECONDS = 2400
NAMES = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
)
REQUIREMENT = (
    "Make an agent for recordings. I give it a recording (like the video of a one hour event) and ask questions about "
    "it, and it should answer and tell me from which moment to play. First POST /recordings/<id>/index, body {}: it "
    "goes through the recording, finds its parts and stores the parts with their descriptions and times in tables, so "
    "that it is fast when the screen is opened again. GET /recordings/<id>/sections returns the stored parts. Then POST "
    '/recordings/<id>/ask with {"question": "..."} answers with {"found": true or false, "answer": "...", '
    '"start_seconds": n, "end_seconds": n}; the part to play must be short. When the recording does not say it, found '
    "is false. After indexing, later questions should use the stored data and not analyse the full recording every "
    "time. Test it with recording 13615: for example, how many cash machines does the bank have? (more than 50,000, "
    "said at 00:04:20)."
)
# question -> (words of which one must be in the answer, the second it is at; None: not in the recording)
QUESTIONS: dict[str, tuple[tuple[str, ...], int | None]] = {
    "How many ATMs does the bank run?": (("50,000", "50000", "fifty thousand"), 260),
    "By how much did housing loans grow?": (("14",), 1880),
    "What is the colour of the map of India shown in the video?": (("orange", "saffron"), 560),
    "Which animal can be seen on the speaker's mug?": (("elephant",), 1400),
    "What is written on the sticker in the server room?": (("site b",), 3500),
    "What unusual headgear appears in the team picture?": (("cowboy",), 3980),
    "What time does the clock on the wall show?": (
        ("4:10", "ten past four", "10 past 4", "4.10", "16:10"),
        3140,
    ),
    "What does the chief executive say about opening a bank on the Moon?": ((), None),
}


def start(folder: Path, port: int, env: dict[str, str]) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "recqa.server"],
        cwd=folder,
        env={**os.environ, **env, "RECQA_PORT": str(port), "RECQA_DB": str(folder / "check.db")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and process.poll() is None:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return process
        time.sleep(0.2)
    process.kill()
    raise RuntimeError("RecQA did not start")


def judge(question: str, answer: dict[str, Any]) -> str:
    """'' when right, else what is wrong."""
    words, second = QUESTIONS[question]
    if second is None:
        return "" if answer.get("found") is False else "claims to have found what is not there"
    text = str(answer.get("answer", "")).lower()
    if answer.get("found") is not True:
        return "not found"
    if not any(word in text for word in words):
        return "wrong answer"
    try:
        begin, end = float(answer["start_seconds"]), float(answer["end_seconds"])
    except (KeyError, TypeError, ValueError):
        return "no times"
    if not begin - 60 <= second <= end + 60:
        return "wrong moment"
    return "" if end - begin <= 300 else f"plays {end - begin:.0f} s"


async def test_debcraft_builds_answers_to_questions_it_never_saw(
    tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not VENV_PYTHON.is_file():
        pytest.skip("the fixture venv is missing (tests/fixtures/agent_platform_pg/requirements.txt)")
    own = {
        k: v
        for file in (
            REPO_ROOT / ".env",
            Path.home() / ".forge" / ".env",
        )  # the second has the gpt-5.4 deployment
        for k, v in dotenv_values(file).items()
        if v
    }
    if not own.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(
        "\n".join(f"{k}={v}" for k, v in own.items() if not k.endswith("PG_URL")) + "\n", encoding="utf-8"
    )
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE, repo, ignore=shutil.ignore_patterns("__pycache__", "*.db"))
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(repo / "venv"), str(APP_VENV)], check=True, capture_output=True
        )
    else:
        (repo / "venv").symlink_to(APP_VENV)
    secrets = load_secrets(isolated_forge_home)
    workspace = create_workspace(repo, tmp_path / "ws", "")
    save_grant(workspace, "gpt51")
    config = load_config(isolated_forge_home)
    # a clean home has the shipped default roles; the user's coder is gpt-5.4 (D-446)
    config.llm.roles.coder = os.environ.get("RECQA_CODER", "gpt54")
    effort = os.environ.get("RECQA_EFFORT")
    if effort:
        config.llm.role_reasoning_effort["coder"] = effort
    host = SessionHost(
        LLMRouter(config, secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        permission_mode="auto",
        secrets=secrets,
    )
    calls: list[str] = []
    notices: list[str] = []
    said: list[str] = []

    def reply(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_STARTED:
            calls.append(f"{event.payload['name']} {event.payload['arguments']}"[:200])
        if event.type == EventType.NOTICE:
            notices.append(str(event.payload.get("kind")))
        if event.type == EventType.MESSAGE_DONE:
            said.append(str(event.payload.get("text", "")))
        if event.type == EventType.USER_ACTION_REQUESTED:
            return Answer(question_id=event.payload["id"], choice="done", text=None)
        return auto_reply(event, auto_approve=True)

    began = time.monotonic()
    finished = False
    runner = asyncio.create_task(host.run())
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    await host.submit(SendMessage(text=REQUIREMENT))
    try:
        async with asyncio.timeout(TURN_SECONDS):
            async for event in subscription:
                if (answer := reply(event)) is not None:
                    await host.submit(answer)
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    finished = True
                    break
    except TimeoutError:
        pass
    finally:
        subscription.close()
        runner.cancel()
        await host.close()
    seconds = round(time.monotonic() - began)
    keep = os.environ.get("RUNNING_SYSTEM_KEEP")
    if keep:
        target = Path(keep) / "recording_qa"
        shutil.copytree(
            workspace.repo_dir, target / "repo", ignore=shutil.ignore_patterns("venv", "__pycache__")
        )
        shutil.copy(workspace.forge_dir / "events.jsonl", target / "events.jsonl")
    check = tmp_path / "check"
    shutil.copytree(workspace.repo_dir, check, ignore=shutil.ignore_patterns("__pycache__", "venv", "*.db"))
    port = free_port()
    results: dict[str, dict[str, Any]] = {}
    index_status = sections_status = 0
    process = start(check, port, {name: own[name] for name in NAMES if name in own})
    try:
        base = f"http://127.0.0.1:{port}/recordings/13615"
        index_status = httpx.post(f"{base}/index", json={}, timeout=900).status_code
        sections_status = httpx.get(f"{base}/sections", timeout=60).status_code
        for question in QUESTIONS:
            started = time.monotonic()
            answer: dict[str, Any]
            try:
                answer = httpx.post(f"{base}/ask", json={"question": question}, timeout=300).json()
            except (httpx.HTTPError, ValueError) as error:
                answer = {"error": type(error).__name__}
            results[question] = {
                "problem": judge(question, answer),
                "answer": str(answer.get("answer", answer))[:200],
                "span": [answer.get("start_seconds"), answer.get("end_seconds")],
                "seconds": round(time.monotonic() - started, 1),
            }
    finally:
        process.kill()
        process.wait(timeout=10)
    right = sum(1 for r in results.values() if not r["problem"])
    row = {
        "scenario": "recording_qa",
        "finished": finished,
        "seconds": seconds,
        "right": right,
        "of": len(QUESTIONS),
        "index_status": index_status,
        "sections_status": sections_status,
        "calls": len(calls),
        "notices": [n for n in notices if n != "usage"],
        "results": results,
        "said": "\n".join(said)[-1500:],
        "tools": [c.split(" ")[0] for c in calls],
    }
    if os.environ.get("RUNNING_SYSTEM_LOG"):
        with open(os.environ["RUNNING_SYSTEM_LOG"], "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    print("\n" + json.dumps(row, indent=1))
    assert index_status == 200 and sections_status == 200
    assert right == len(QUESTIONS), {q: r["problem"] for q, r in results.items() if r["problem"]}
