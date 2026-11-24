"""Which model thinks best? The same tasks on GPT and Gemini models, recorded side by side (D-653).

    .venv\\Scripts\\python scripts\\dev\\thinking_test.py --check          only: which models answer here (a minute)
    .venv\\Scripts\\python scripts\\dev\\thinking_test.py --quick          each task once (about 15 minutes)
    .venv\\Scripts\\python scripts\\dev\\thinking_test.py                  each task twice (about 30 minutes)
    ... --models gpt54,gemini-4-argon                                     only these

It reads the keys the way DebCraft does and prints none. Results go to <DebCraft Home>\\reports\\thinking-<time>.md (the
table is what to photograph) and .json (every answer). Three kinds of task: questions with one right answer, code that
must pass hidden checks (run in a separate Python process with a time limit), and design answers scored blind against
yes/no criteria by two judge models. No project, no file and no data of the user is sent: the tasks are in this file."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.config import ModelConfig, forge_home, load_config, load_secrets
from forge.errors import ForgeError, LLMError, LLMRateLimitError
from forge.llm.base import ChatRequest, Message
from forge.llm.router import LLMRouter
from forge.net import use_system_certificates

GPT = ("gpt54", "gpt52", "gpt51")
GEMINI = (
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-4-hydrogen",
    "gemini-4-neon",
    "gemini-3.1-pro-preview",
)
EFFORTS = {"azure": ("medium", "high"), "gemini": (None, "high")}
JUDGES = ("gpt52", "gemini-3.1-pro-preview", "gpt51", "gemini-4-argon")
CALL_TIMEOUT_S = 300
MAX_WAIT_S = 180

EXACT: dict[str, tuple[str, Any]] = {
    "two tokens": (
        "A local app checks incoming tokens with key L. Its /index endpoint then forwards the caller's token unchanged "
        "to a remote file service, which checks tokens with key D. L and D differ. What happens when /index is called "
        "with (a) a token signed with L, (b) a token signed with D? And which ONE change makes a token signed with D work "
        "end to end without changing the app's code: A) give the local app key D as its checking key, B) sign a new "
        "token with L, C) return an empty result when the file service answers 422, D) raise the timeout? Answer with "
        'JSON only: {"a": "fails_at_app|fails_at_file_service|works", "b": "...", "change": "A|B|C|D"}',
        {"a": "fails_at_file_service", "b": "fails_at_app", "change": "A"},
    ),
    "criterion that blocks the goal": (
        "Goal: users ask ANY question about an uploaded video and get the right answer, also about details nobody "
        "described beforehand. Criteria: 1 The video is indexed once and its sections are stored. 2 Stored sections are "
        "shown when the screen is opened again. 3 Each answer has a start and an end time. 4 Questions are answered "
        "only from the stored section descriptions. 5 When the video does not contain the answer, the reply says so. "
        '6 Long videos keep correct times. Which criterion makes the goal impossible? JSON only: {"criterion": n}',
        {"criterion": 4},
    ),
    "interleaving": (
        "import asyncio\ntotal = 0\nasync def add(n):\n    global total\n    seen = total\n    await asyncio.sleep(0)\n"
        "    total = seen + n\nasync def main():\n    await asyncio.gather(add(1), add(2), add(4))\n    print(total)\n"
        'asyncio.run(main())\nWhat does this Python program print? JSON only: {"prints": n}',
        {"prints": 4},
    ),
    "paging while deleting": (
        "A table has rows 1 to 10. A job loops: SELECT id FROM t ORDER BY id LIMIT 3 OFFSET :o (o starts at 0 and grows by "
        "3 after each page); it processes and then DELETEs the rows of the page; it stops at the first empty page. Which "
        'rows are never processed? JSON only: {"never": [ids in order]}',
        {"never": [4, 5, 6, 10]},
    ),
    "null in a subquery": (
        "Table a(id) holds 1, 2, 3. Table b(a_id) holds 1 and NULL. How many rows does this return in PostgreSQL: SELECT "
        'id FROM a WHERE id NOT IN (SELECT a_id FROM b)? JSON only: {"rows": n}',
        {"rows": 0},
    ),
    "closures": (
        "fs = [lambda x, i=i: x * i for i in range(3)]\ngs = [lambda x: x * i for i in range(3)]\n"
        "print(sum(f(10) for f in fs), sum(g(10) for g in gs))\nWhat does this Python program print? "
        'JSON only: {"first": n, "second": n}',
        {"first": 30, "second": 60},
    ),
}

CODE: dict[str, tuple[str, str]] = {
    "parse_time": (
        "Write a Python function parse_time(text: str) -> int that returns seconds for 'HH:MM:SS', 'MM:SS' or 'SS'. "
        "Every part is one or more ASCII digits. With hours, minutes and seconds must be below 60. With 'MM:SS', minutes may "
        "be 60 or more and seconds must be below 60. 'SS' alone may be any number. Anything else (spaces, signs, empty "
        "parts, decimals, more than three parts) raises ValueError. Answer with one Python code block only.",
        """
assert parse_time("01:22:15") == 4935 and parse_time("82:15") == 4935 and parse_time("4935") == 4935
assert parse_time("0:0:0") == 0 and parse_time("100:00:59") == 360059 and parse_time("00:59") == 59
for bad in ("", "1:60:00", "1:00:60", "5:60", " 5", "5 ", "-1", "+1", "1.5", "1::2", ":5", "5:", "1:2:3:4", "a", "1:2 :3", "\\u0661", "1_0", "5\\n"):
    try:
        parse_time(bad)
    except ValueError:
        continue
    raise AssertionError(bad)
""",
    ),
    "merge_parts": (
        "Write a Python function merge_parts(parts, gap, limit) where parts is a list of (start, end) numbers in any order. "
        "Parts with end <= start are ignored. Parts that overlap, or whose distance is at most gap, are joined. Then every "
        "joined part longer than limit is cut from its start into pieces of exactly limit; the last piece may be shorter. "
        "Return a list of (start, end) tuples in order. Do not change the input. Answer with one Python code block only.",
        """
data = [(10, 20), (0, 5), (6, 9), (30, 30), (50, 40)]
assert merge_parts(data, 1, 100) == [(0, 20)] and data == [(10, 20), (0, 5), (6, 9), (30, 30), (50, 40)]
assert merge_parts(data, 0, 100) == [(0, 5), (6, 9), (10, 20)]
assert merge_parts([(0, 100), (10, 20), (101, 130)], 1, 60) == [(0, 60), (60, 120), (120, 130)]
assert merge_parts([(0, 60)], 0, 60) == [(0, 60)] and merge_parts([], 5, 5) == []
assert merge_parts([(0, 10), (10, 20)], 0, 100) == [(0, 20)]
assert merge_parts([(5, 6), (0, 10), (9, 12)], 0, 100) == [(0, 12)]
""",
    ),
    "cache": (
        "Write a Python class Cache with __init__(capacity, ttl), put(key, value, now) and get(key, now). get returns the "
        "value or None. An entry is expired when now - time of its last put >= ttl; an expired entry is never returned and "
        "never counts toward capacity. When a put of a new key would exceed capacity, the least recently used entry is "
        "removed (a get that returns a value and a put both count as use). A get does not extend the ttl. A put of an "
        "existing key replaces its value and starts its ttl again. capacity is at least 1. Answer with one Python code "
        "block only.",
        """
c = Cache(2, 10)
c.put("a", 1, 0); c.put("b", 2, 1)
assert c.get("a", 2) == 1
c.put("c", 3, 3)
assert c.get("b", 4) is None and c.get("a", 4) == 1 and c.get("c", 4) == 3
assert c.get("a", 10) is None and c.get("c", 12) == 3 and c.get("c", 13) is None
c = Cache(2, 10)
c.put("a", 1, 0); c.put("b", 2, 5); c.get("a", 9)
c.put("c", 3, 11)
assert c.get("b", 12) == 2 and c.get("c", 12) == 3 and c.get("a", 12) is None
c = Cache(1, 5)
c.put("a", 1, 0); c.put("a", 2, 4)
assert c.get("a", 8) == 2 and c.get("a", 9) is None
c = Cache(2, 100)
c.put("a", 1, 0); c.put("b", 2, 1); c.put("a", 3, 2); c.put("c", 4, 3)
assert c.get("b", 4) is None and c.get("a", 4) == 3
c = Cache(2, 10)
c.put("a", None, 0); c.put("b", 0, 0)
assert c.get("b", 1) == 0
""",
    ),
}

DESIGN: dict[str, tuple[str, list[str]]] = {
    "video agent": (
        "Requirement: I upload a video (up to 1.5 hours; CCTV without sound, or a training video). I ask a question; the "
        "agent answers and the screen plays the video from that moment. Indexing once should store sections and "
        "descriptions so the screen opens fast later. The backend is Flask with PostgreSQL; a multimodal model that "
        "accepts video is available; the video is fetched from a file service with the caller's token. Give the approach "
        "you would build (at most 450 words): how a question is answered step by step, what is stored, what can go wrong, "
        "and how you would prove that it works.",
        [
            "A language model, not keyword or word-overlap matching alone, decides which stored sections are relevant or answers the question",
            "When the stored descriptions do not contain the answer, the video itself (or parts of it) is given to the model with the question",
            "It says what happens when the video does not contain the answer, without inventing one",
            "It deals with the length of the video (splitting it, or limits of the model) with correct absolute times",
            "What was found by looking again is stored or cached for later questions",
            "It notices that the caller's token is passed to the file service and what that means (expiry, or a token valid in both places)",
            "It proves the result with questions that were not used while building, including details that are not in the descriptions",
            "Parts to play are short enough to start at the moment asked for",
        ],
    ),
    "wrong answer reported": (
        "An agent answers questions about a video from stored section texts. It scores sections by how many words they "
        "share with the question and returns the best sentence. A user reports: the question 'What is the colour of the map "
        "of India shown?' was answered with 'We have the biggest ATM network' (confidence 0.857, reason: matched keywords "
        "the, the, map, india, shown). The text of what is seen never mentions a colour. A model that can watch the video is "
        "available. What is the cause, and what would you change? At most 300 words, the most important first.",
        [
            "It names the general cause: word overlap does not measure meaning or whether the answer is contained",
            "It does not propose special rules for particular words or question types (such as colour questions or stop words) as the main fix",
            "It uses a model to judge relevance or to answer from the sections",
            "When the sections do not contain the answer, it asks the model with the video itself",
            "It prevents an unrelated sentence from being returned (not found, or a check that the source supports the answer)",
            "It says that the confidence number is meaningless or must be grounded",
            "It would check the fix with several other questions that fail in the same way, not only with this one",
        ],
    ),
}


@dataclass
class Variant:
    name: str
    provider: Any
    router_key: str
    effort: str | None
    exact: int = 0
    code: int = 0
    design: list[float] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)
    thinking: list[int] = field(default_factory=list)
    errors: int = 0
    answers: list[dict[str, Any]] = field(default_factory=list)


def build_router(wanted: list[str]) -> tuple[LLMRouter, dict[str, str]]:
    """The router with every candidate added, and name -> config key."""
    config = load_config(forge_home())
    keys = {key: key for key in GPT if key in config.llm.models}
    for name in GEMINI:
        known = next((k for k, m in config.llm.models.items() if m.model_name == name), None)
        if known is None:
            known = re.sub(r"\W", "", name)
            config.llm.models[known] = ModelConfig(
                provider="gemini", label=name, model_name=name, context_window=1_000_000, max_output=32000
            )
        keys[name] = known
    router = LLMRouter(config, load_secrets(forge_home()))
    return router, {name: key for name, key in keys.items() if not wanted or name in wanted}


async def ask(provider: Any, key: str, prompt: str, effort: str | None) -> tuple[Any, float]:
    """One answer and the seconds of the call that succeeded; waits when the model is busy."""
    waited = 0.0
    while True:
        began = time.perf_counter()
        try:
            request = ChatRequest(
                messages=[Message.user(prompt)], max_output_tokens=16000, reasoning_effort=effort
            )
            response = await asyncio.wait_for(provider.chat(request), CALL_TIMEOUT_S)
            return response, time.perf_counter() - began
        except LLMRateLimitError as error:
            delay = min(max(error.retry_after_s or 15.0, 5.0), 60.0)
            if waited + delay > MAX_WAIT_S:
                raise
            waited += delay
            await asyncio.sleep(delay)


def json_in(text: str) -> dict[str, Any] | None:
    for found in reversed(re.findall(r"\{[^{}]*\}", text, re.DOTALL)):
        try:
            data = json.loads(found)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def code_in(text: str) -> str:
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return max(blocks, key=len) if blocks else text


def passes(code: str, checks: str) -> bool:
    """The answer and the hidden checks in a separate Python, in an empty folder, for at most 20 seconds."""
    with tempfile.TemporaryDirectory() as folder:
        file = Path(folder) / "answer.py"
        file.write_text(code + "\n\n" + checks, encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, "-I", str(file)], cwd=folder, capture_output=True, timeout=20, check=False
            )
        except subprocess.TimeoutExpired:
            return False
        return done.returncode == 0


async def judge(
    judges: list[tuple[str, Any]], question: str, criteria: list[str], answer: str
) -> float | None:
    """The share of criteria met, the mean of the judges; they see the answer only, not who wrote it."""
    listing = "\n".join(f"{n}. {text}" for n, text in enumerate(criteria, 1))
    prompt = (
        "Score an answer against criteria. A criterion is met only when the answer really says it; be strict and do not "
        f"reward length.\n\nThe question was:\n{question}\n\nThe answer:\n{answer}\n\nCriteria:\n{listing}\n\n"
        'JSON only: {"met": [numbers of the criteria that are met]}'
    )
    scores = []
    for _, provider in judges:
        try:
            response, _ = await ask(provider, "", prompt, None)
        except (LLMError, TimeoutError, ForgeError):
            continue
        data = json_in(response.text)
        if data is not None and isinstance(data.get("met"), list):
            met = {n for n in data["met"] if isinstance(n, int) and 1 <= n <= len(criteria)}
            scores.append(len(met) / len(criteria))
    return sum(scores) / len(scores) if scores else None


async def available(router: LLMRouter, keys: dict[str, str]) -> dict[str, Any]:
    print("== Which models answer here ==", flush=True)
    found: dict[str, Any] = {}
    for name, key in keys.items():
        model = router.config.llm.models[key]
        try:
            if not router._configured(key):
                raise ForgeError("not set up in the .env file")
            provider = router.provider(key)
            response, seconds = await ask(provider, key, "Reply with the single word: ready", None)
            found[name] = provider
            print(
                f"  yes  {name:26} {seconds:5.1f} s   served as {response.served_model or model.model_name}",
                flush=True,
            )
        except (LLMError, ForgeError, TimeoutError, ImportError) as error:
            print(
                f"  NO   {name:26} {type(error).__name__}: {' '.join(str(error).split())[:110]}", flush=True
            )
    return found


async def run_variant(variant: Variant, judges: list[tuple[str, Any]], repeats: int) -> None:
    async def one(kind: str, task: str, prompt: str, check: Any) -> None:
        try:
            response, seconds = await ask(variant.provider, variant.router_key, prompt, variant.effort)
        except (LLMError, ForgeError, TimeoutError) as error:
            variant.errors += 1
            variant.answers.append({"task": task, "error": f"{type(error).__name__}: {str(error)[:200]}"})
            return
        variant.seconds.append(seconds)
        variant.thinking.append(response.usage.reasoning_tokens)
        result = await check(response.text)
        if kind == "exact":
            variant.exact += bool(result)
        elif kind == "code":
            variant.code += bool(result)
        elif result is not None:
            variant.design.append(result)
        variant.answers.append(
            {"task": task, "result": result, "seconds": round(seconds, 1), "answer": response.text}
        )

    for _ in range(repeats):
        for task, (prompt, right) in EXACT.items():

            async def same(text: str, right: Any = right) -> bool:
                return json_in(text) == right

            await one("exact", task, prompt, same)
        for task, (prompt, checks) in CODE.items():

            async def runs(text: str, checks: str = checks) -> bool:
                return await asyncio.to_thread(passes, code_in(text), checks)

            await one("code", task, prompt, runs)
        for task, (prompt, criteria) in DESIGN.items():

            async def scored(text: str, prompt: str = prompt, criteria: list[str] = criteria) -> float | None:
                return await judge(judges, prompt, criteria, text)

            await one("design", task, prompt, scored)
    print(f"  done {variant.name}", flush=True)


def mean(values: list[float] | list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def table(variants: list[Variant], repeats: int) -> list[str]:
    exact, code = len(EXACT) * repeats, len(CODE) * repeats
    out = [
        f"{'model':36} {'answers':>8} {'code':>6} {'design':>7} {'seconds':>8} {'thinking':>9} {'errors':>7}"
    ]

    def rank(v: Variant) -> float:
        return v.exact / exact + v.code / code + mean(v.design)

    for v in sorted(variants, key=rank, reverse=True):
        design = f"{mean(v.design) * 100:.0f}%" if v.design else "-"
        out.append(
            f"{v.name:36} {f'{v.exact}/{exact}':>8} {f'{v.code}/{code}':>6} {design:>7} {mean(v.seconds):8.1f} "
            f"{mean(v.thinking):9.0f} {v.errors:7}"
        )
    return out


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="only list which models answer")
    parser.add_argument("--quick", action="store_true", help="each task once")
    parser.add_argument("--models", default="", help="comma separated names; default: all that answer")
    args = parser.parse_args()
    use_system_certificates()
    wanted = [m.strip() for m in args.models.split(",") if m.strip()]
    router, keys = build_router([])
    found = await available(
        router, {n: k for n, k in keys.items() if not wanted or n in wanted or n in JUDGES}
    )
    if args.check:
        return 0
    judges = [(name, found[name]) for name in JUDGES if name in found][:2]
    testing = [name for name in found if not wanted or name in wanted]
    if not testing or not judges:
        print("Nothing to compare: no model answered.")
        return 1
    variants = [
        Variant(f"{name} ({effort or 'default'})", found[name], keys[name], effort)
        for name in testing
        for effort in EFFORTS[router.config.llm.models[keys[name]].provider]
    ]
    repeats = 1 if args.quick else 2
    print(
        f"\n== {len(variants)} variants, each task {repeats}x; judges: {', '.join(n for n, _ in judges)} ==",
        flush=True,
    )
    began = time.perf_counter()
    # one model at a time per provider name, so a model's own rate limit does not slow another down
    groups: dict[str, list[Variant]] = {}
    for variant in variants:
        groups.setdefault(variant.router_key, []).append(variant)

    async def run_group(group: list[Variant]) -> None:
        for variant in group:
            await run_variant(variant, judges, repeats)

    await asyncio.gather(*(run_group(group) for group in groups.values()))
    lines = table(variants, repeats)
    note = (
        f"answers: questions with one right answer; code: passed the hidden checks; design: share of criteria met, scored "
        f"blind by {', '.join(n for n, _ in judges)} (a judge may favour its own family); seconds and thinking tokens: "
        f"mean per call, waits for quota not counted. {time.perf_counter() - began:.0f} s in all."
    )
    print("\n" + "\n".join(lines) + "\n\n" + note, flush=True)
    folder = forge_home() / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    failed = [
        f"- {v.name}: {a['task']}" + (f" ({a['error']})" if "error" in a else "")
        for v in variants
        for a in v.answers
        if a.get("result") is False or "error" in a
    ]
    text = [
        "# Thinking test",
        "",
        "```",
        *lines,
        "```",
        "",
        note,
        "",
        "## What went wrong",
        "",
        *(failed or ["nothing"]),
    ]
    (folder / f"thinking-{stamp}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    (folder / f"thinking-{stamp}.json").write_text(
        json.dumps({v.name: v.answers for v in variants}, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"\nSaved: {folder / f'thinking-{stamp}.md'}  (photograph the table; the .json next to it holds the answers)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
