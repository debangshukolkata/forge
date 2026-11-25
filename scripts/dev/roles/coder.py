"""Coder: DebCraft itself builds the recording agent and repairs a reported fault, with one model in every role (D-655).

Every run has its own project, its own DebCraft Home and no fallback model, so nobody else does part of the work. The
project asks one fixed model through a small local address, so no key is in the project and every candidate builds on
the same model. Nothing of the user's projects is used, and no database of the user is reachable."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import venv
from collections import Counter
from collections.abc import Awaitable, Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx

from forge.config import ForgeConfig, Secrets
from forge.engine.headless import auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, Interrupt, SendMessage, UserInput
from forge.workspace.create import create_workspace

FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "recording_qa"
BUILD_SECONDS = 2100
REPAIR_SECONDS = 1200
BUILD = (
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
REPAIR = (
    "GET /recordings/20417 gives no answer at all, the connection is closed. The file recordings/20417.txt comes from "
    "another camera; files like it will come every day. Make it work."
)
# question -> (words of which one must be in the answer, the second it is at; None: not in the recording)
QUESTIONS: dict[str, tuple[tuple[str, ...], int | None]] = {
    "How many ATMs does the bank run?": (("50,000", "50000", "fifty thousand"), 260),
    "By how much did housing loans grow?": (("14", "fourteen"), 1880),
    "How long until I get a new card after blocking mine?": (("four", "4 day"), 2300),
    "What is the colour of the map of India shown in the video?": (("orange", "saffron"), 560),
    "Which animal can be seen on the speaker's mug?": (("elephant",), 1400),
    "What is written on the sticker in the server room?": (("site b",), 3500),
    "What unusual headgear appears in the team picture?": (("cowboy",), 3980),
    "What time does the clock on the wall show?": (
        ("4:10", "ten past four", "10 past 4", "4.10", "16:10"),
        3140,
    ),
    "What colour is the umbrella of the woman with the form?": (("yellow",), 2780),
    "What do we see on the very last slide?": (("crane",), 4760),
    "What does the chief executive say about opening a bank on the Moon?": ((), None),
    "How many branches does the bank have in Brazil?": ((), None),
}
MODEL_PY = '''"""The language model of the service, behind a local address (RECQA_MODEL_URL)."""

from __future__ import annotations

import json
import os
import urllib.request

ADDRESS = os.environ.get("RECQA_MODEL_URL", "http://127.0.0.1:{port}/complete")


def complete(prompt: str, json_answer: bool = False) -> str:
    """The model's answer to one prompt. `json_answer`: it answers with one JSON object (say so in the prompt)."""
    body = json.dumps({{"prompt": prompt, "json": json_answer}}).encode()
    request = urllib.request.Request(ADDRESS, body, {{"Content-Type": "application/json"}})
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({{}}))  # this machine, never through a proxy
    with direct.open(request, timeout=150) as answer:
        return json.loads(answer.read())["text"]
'''
README = """# RecQA

A small service for recordings. A recording is a text file in `recordings/<id>.txt`: one line per moment,
`HH:MM:SS | speech: ... | screen: ...` (what is said and what is seen), as a video would be given to a model.

- `recqa/server.py` the HTTP API, `recqa/recordings.py` reads a recording, `recqa/store.py` SQLite,
  `recqa/model.py` the language model (`complete(prompt)`; it is running and needs no key).
- Start: `python -m recqa.server` (port from `RECQA_PORT`, default 8790). Only the standard library is used.
"""
# what the user reports, and two files of the same kind nobody mentioned: (file text, moments, seconds of the last one)
CAMERA: dict[str, tuple[str, int, int]] = {
    "20417": (
        "00:05 | speech: good morning | screen: an empty hall\n"
        "01:10 | speech: the doors are open | screen: people come in\n"
        "59:40 | speech: that is all for now | screen: a closed door\n",
        3,
        3580,
    ),
    "20418": (
        "00:05 | speech: the menu says soup | salad | screen: a board with two lines\n\n"
        "10:20 | speech: next please | screen: a queue\n\n",
        2,
        620,
    ),
    "20419": (
        "00:00:30 | speech: we begin | screen: a stage\n58:15 | speech: a short break | screen: a clock\n"
        "1:02:09 | speech: and the end | screen: an empty stage\n",
        3,
        3729,
    ),
}
Complete = Callable[[str, bool], Awaitable[str]]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class ModelServer:
    """The one model every candidate's application asks; the calls run on the event loop of the challenge."""

    def __init__(self, complete: Complete, loop: asyncio.AbstractEventLoop) -> None:
        outer = self
        self.calls = 0

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                outer.calls += 1
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        complete(str(data.get("prompt", "")), bool(data.get("json"))), loop
                    )
                    status, body = 200, {"text": future.result(timeout=140)}
                except Exception as error:
                    status, body = 503, {"error": type(error).__name__}
                raw = json.dumps(body).encode()
                with contextlib.suppress(OSError):  # the application may have given up waiting
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def make_project(folder: Path, model_port: int) -> Path:
    repo = folder / "repo"
    shutil.copytree(FIXTURE, repo, ignore=shutil.ignore_patterns("__pycache__", "*.db", "requirements.txt"))
    (repo / "recqa" / "model.py").write_text(MODEL_PY.format(port=model_port), encoding="utf-8")
    (repo / "README.md").write_text(README, encoding="utf-8")
    (repo / "recordings" / "20417.txt").write_text(CAMERA["20417"][0], encoding="utf-8")
    venv.create(repo / "venv", with_pip=False)
    return repo


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


def count_right(results: dict[str, dict[str, Any]]) -> int:
    """Questions answered right. An application that never finds anything gets nothing for what is not there."""
    right = [question for question, result in results.items() if not result["problem"]]
    return len(right) if any(QUESTIONS[question][1] is not None for question in right) else 0


def points(right: int, camera: dict[str, bool]) -> float:
    """The product: 70 percent the unseen questions, 30 percent the reported fault and its relatives."""
    return round(70 * right / len(QUESTIONS) + 30 * sum(camera.values()) / len(camera), 1)


class Application:
    """The result, started from a copy."""

    def __init__(self, source: Path, copy: Path, model_port: int) -> None:
        shutil.rmtree(copy, ignore_errors=True)
        shutil.copytree(source, copy, ignore=shutil.ignore_patterns("__pycache__", "venv", "*.db", ".git"))
        for name, (text, _, _) in CAMERA.items():
            (copy / "recordings" / f"{name}.txt").write_text(text, encoding="utf-8")
        port = free_port()
        self.base = f"http://127.0.0.1:{port}/recordings"
        address = f"http://127.0.0.1:{model_port}/complete"
        self.process = subprocess.Popen(
            [sys.executable, "-m", "recqa.server"],
            cwd=copy,
            env={
                **os.environ,
                "RECQA_PORT": str(port),
                "RECQA_DB": str(copy / "check.db"),
                "RECQA_MODEL_URL": address,
                "PYTHONPATH": str(copy),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 20
        self.runs = False
        while time.monotonic() < deadline and self.process.poll() is None and not self.runs:
            with socket.socket() as probe:
                self.runs = probe.connect_ex(("127.0.0.1", port)) == 0
            time.sleep(0.2)

    def call(self, method: str, path: str, body: Any = None, timeout: float = 200) -> tuple[int, Any]:
        try:
            with httpx.Client(trust_env=False, timeout=timeout) as client:
                answer = client.request(method, f"{self.base}/{path}", json=body)
            return answer.status_code, answer.json()
        except (httpx.HTTPError, ValueError) as error:
            return 0, {"error": type(error).__name__}

    def close(self) -> None:
        self.process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.process.wait(timeout=10)


def check_answers(source: Path, copy: Path, model_port: int) -> dict[str, Any]:
    app = Application(source, copy, model_port)
    results: dict[str, dict[str, Any]] = {}
    try:
        index, _ = app.call("POST", "13615/index", {}, timeout=900) if app.runs else (0, None)
        sections, _ = app.call("GET", "13615/sections") if app.runs else (0, None)
        for question in QUESTIONS:
            began = time.monotonic()
            _, answer = app.call("POST", "13615/ask", {"question": question}) if app.runs else (0, {})
            answer = answer if isinstance(answer, dict) else {}
            results[question] = {
                "problem": judge(question, answer),
                "answer": str(answer.get("answer", answer))[:160],
                "seconds": round(time.monotonic() - began, 1),
            }
    finally:
        app.close()
    return {"starts": app.runs, "index": index, "sections": sections, "results": results}


def check_camera(source: Path, copy: Path, model_port: int) -> dict[str, bool]:
    app = Application(source, copy, model_port)
    try:
        good = {}
        for name, (_, moments, seconds) in CAMERA.items():
            status, data = app.call("GET", name, timeout=20) if app.runs else (0, {})
            good[name] = status == 200 and data.get("moments") == moments and data.get("seconds") == seconds
        status, data = app.call("GET", "13615", timeout=20) if app.runs else (0, {})
        good["13615 still works"] = status == 200 and data.get("moments") == 246
        return good
    finally:
        app.close()


async def _turn(
    host: SessionHost, text: str, limit: float, counted: Counter[str], failed: list[str]
) -> tuple[bool, int]:
    """One request of the user to its end: (finished in time, seconds)."""
    finished = False
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)

    def reply(event: Event) -> UserInput | None:
        if event.type == EventType.TOOL_CALL_FINISHED:
            counted[str(event.payload.get("name"))] += 1
            if not event.payload.get("ok"):
                failed.append(str(event.payload.get("name")))
        if event.type == EventType.USER_ACTION_REQUESTED:
            return Answer(question_id=event.payload["id"], choice="done", text=None)
        return auto_reply(event, auto_approve=True)

    began = time.monotonic()
    await host.submit(SendMessage(text=text))
    try:
        async with asyncio.timeout(limit):
            async for event in subscription:
                if (answer := reply(event)) is not None:
                    await host.submit(answer)
                if event.type == EventType.ERROR:
                    failed.append(
                        "ERROR " + str(event.payload.get("text") or event.payload.get("message"))[:120]
                    )
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    finished = event.type == EventType.COST_UPDATED
                    break
    except TimeoutError:
        await host.submit(Interrupt())
        await asyncio.sleep(3)
    finally:
        subscription.close()
    return finished, round(time.monotonic() - began)


def alone(config: ForgeConfig, key: str) -> ForgeConfig:
    """The configuration with this one model in every role and nobody to fall back to."""
    mine = config.model_copy(deep=True)
    for role in ("coder", "reviewer", "summariser", "vision", "judge", "critic", "planner", "fallback"):
        setattr(mine.llm.roles, role, key)
    mine.llm.rotation = []
    mine.llm.fallback_also = []
    mine.llm.gemini_on_quota = "never"
    return mine


def own_secrets(secrets: Secrets) -> Secrets:
    """The model keys only: no database and no other service of the user is reachable from the test."""
    wanted = ("AZURE_", "GOOGLE_", "GEMINI_")
    return Secrets({n: v for n in secrets.names() if n.startswith(wanted) and (v := secrets.get(n))}, None)


async def run(
    config: ForgeConfig, secrets: Secrets, key: str, folder: Path, model_port: int
) -> dict[str, Any]:
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    home_before = os.environ.get("FORGE_HOME")
    os.environ["FORGE_HOME"] = str(
        folder / "home"
    )  # nothing learned here reaches the user's DebCraft, and back
    (folder / "home").mkdir()
    try:
        repo = make_project(folder, model_port)
        workspace = create_workspace(repo, folder / "ws", "")
        router = LLMRouter(alone(config, key), own_secrets(secrets))
        host = SessionHost(
            router,
            EventBus(workspace.forge_dir / "events.jsonl"),
            workspace=workspace,
            permission_mode="auto",
            secrets=own_secrets(secrets),
        )
        counted: Counter[str] = Counter()
        failed: list[str] = []
        runner = asyncio.create_task(host.run())
        try:
            built, seconds = await _turn(host, BUILD, BUILD_SECONDS, counted, failed)
            answers = await asyncio.to_thread(check_answers, workspace.repo_dir, folder / "check", model_port)
            repaired, repair_seconds = await _turn(host, REPAIR, REPAIR_SECONDS, counted, failed)
            camera = await asyncio.to_thread(check_camera, workspace.repo_dir, folder / "check", model_port)
        finally:
            runner.cancel()
            await host.close()
        right = count_right(answers["results"])
        served = {
            json.loads(line)["payload"].get("served_model")
            for line in (workspace.forge_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if '"llm_call"' in line
        }
        return {
            "score": points(right, camera),
            "note": f"{right} of {len(QUESTIONS)} questions, fault: {sum(camera.values())} of {len(camera)}, "
            f"{sum(counted.values())} tool calls ({len(failed)} failed)"
            + ("" if built else ", build not finished in time")
            + ("" if repaired else ", repair not finished in time"),
            "seconds": seconds + repair_seconds,
            "build_seconds": seconds,
            "repair_seconds": repair_seconds,
            "finished": built and repaired,
            "right": right,
            "camera": camera,
            "answers": answers,
            "failed_calls": failed[:30],
            "tools": dict(counted),
            "served": sorted(str(s) for s in served if s),
        }
    finally:
        if home_before is None:
            os.environ.pop("FORGE_HOME", None)
        else:
            os.environ["FORGE_HOME"] = home_before
