"""DP2 (D-663): is a plan from two planners better than one? Hydrogen and Argon plan a very complex task, Hydrogen
merges the two plans exactly as DebCraft does (dual_plan), and the three plans are put on one page without the names of
their authors, in a random order, for a judge who is not one of them (Claude, from the user's photographs).

    .venv\\Scripts\\python scripts\\dev\\plan_compare.py              one round (about 10 to 20 minutes)
    ... --rounds 2                                                  two rounds, to see how much a plan varies
    ... --key                which plan is which in the last run: only after the judge's verdict (blind judging)

Everything is saved in <DebCraft Home>\\reports\\plan-compare\\<time>\\: plans.html (the page to photograph; it does not
say which plan is which), the plans as Markdown files and key.json. No project, file or rule of the
user is used; the task is made up and describes its whole system in the text.

Each planner gets the task as one direct call with DebCraft's planner effort, as in the role challenge; inside DebCraft
the planner can also read the repository, which a made-up task does not need."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import random
import string
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import role_challenge as rc

from forge.config import forge_home, load_secrets
from forge.llm.base import ChatRequest, Message
from forge.llm.router import LLMRouter
from forge.net import use_system_certificates
from forge.subagents.dual_plan import MERGE_PROMPT, parse_merge, report

PLANNERS = ("gemini-4-hydrogen", "gemini-4-argon")
MERGER = "gemini-4-hydrogen"

TASK = """You are the planner. Plan the work; do not write code. The builder sees only your plan.

Request of the user:
"Our HTML dashboard agent must stop building dashboards inside the chat request. When I give it a CSV (pasted in the chat
or as an uploaded file) and say what I want to see, it should submit a job to the remote executor and answer at once:
'I have submitted the job, its id is ...'. When I ask later (in the same conversation, or in a new one, or the next day)
'is my dashboard ready?' or 'check job ...', it should check the job and give me the download link when it is done, or
the reason when it failed, in words I understand. The dashboard must be checked before I get it: it must open without
errors, every chart must show the right numbers from my CSV, and nothing in it may send my data anywhere. Several people
use the agent at the same time and must never see each other's jobs. Make it work like the mermaid agent does."

What exists (a Python 3.12 FastAPI service, PostgreSQL, Azure OpenAI through a common LLM gateway):
- Agents are rows in the table `agents` (id, name, system_prompt, tools JSON, model); a handler class per agent in
  `core_features/agents_api/<agent>/handler/`. The chat endpoint `POST /agents/{id}/chat` streams the answer (server-sent
  events) and has the user from the bearer token (`request.state.user_id`, `request.state.tenant_id`).
- Conversations are stored (`conversations`, `messages`); the model sees the last 20 messages of the conversation.
- Uploaded files: `POST /files` stores a file in blob storage and returns `file_id`; `files.read(file_id, user_id)` gives
  the bytes and refuses another user's file. Files up to 200 MB; CSVs from 1 KB to 2 million rows.
- The remote executor ("playground"): `POST /jobs` {"image", "command", "inputs": [{"name", "url"}], "timeout_s"}
  returns {"job_id"}; `GET /jobs/{job_id}` returns {"status": queued|running|completed|failed|expired, "exit_code",
  "logs_url", "outputs": [{"name", "url"}]}; output URLs are signed and valid for 24 hours; jobs are deleted after 7 days.
  It has no callback. At most 20 running jobs per tenant; more are refused with 429. A job is billed per second.
- The mermaid agent already submits a job and returns its id; it keeps nothing about the job, so a job id from another
  conversation or another user can be asked about, and a status check after 24 hours returns a dead link.
- The current dashboard agent builds the HTML inside the chat request with the model, runs a profiler on the CSV
  (`csv_profiler.py`) and two checks on the HTML (tag balance, element ids used by the script); large CSVs time out.

Write the plan in at most 900 words: the approach and why, what is stored and where, the steps of each call, how a job
is checked and what the user is told in each state, the tasks with a check for each, the assumptions and the risks."""

# For the judge only: the plans never see this list. Written before any plan was read.
JUDGE_CHECKS = [
    "Job ownership stored by the service (job id with user and tenant), and every status check verifies it",
    "Finds the user's job without an id ('is my dashboard ready?'), also from a new conversation or the next day",
    "Handles the 24-hour signed links: fresh link or re-signing, never a dead link; and the 7-day deletion",
    "The model never invents the job id or the status: the tool returns them and the code checks them",
    "Pasted CSV and uploaded file both reach the job the same way (stored once, passed by reference, size limits)",
    "Large CSVs: the work (profiling, aggregation, rendering) runs in the job, not in the chat request",
    "The numbers in the charts are computed by code from the CSV, not written by the model, and checked against the data",
    "The dashboard is checked in a real browser in the job (opens without console errors, charts render)",
    "No data leaves: no external scripts/fonts/CDNs, a content security policy or an inlined library, no network calls",
    "Concurrency limit (20 per tenant, 429) handled: queue or clear message, no lost job",
    "Failed and expired jobs explained in plain words from exit code and logs, without dumping logs on the user",
    "Idempotency: asking twice or a retry does not submit two billed jobs",
    "Polling only when asked (no callback), with no busy wait inside the chat request",
    "Fixes the mermaid agent's faults or names them as a shared piece to reuse, not a copy of its behaviour",
    "Tests that prove it: two users, an old job, a failed job, a large CSV, a dashboard with a planted wrong number",
    "Names real, specific risks and assumptions (for example the executor image, cost per second, model JSON)",
]


def page(labelled: dict[str, str], round_number: int) -> str:
    parts = [f"<h2>Round {round_number}</h2>"]
    for label, text in labelled.items():
        parts.append(f"<h3>{label}</h3><pre>{html.escape(text)}</pre>")
    return "\n".join(parts)


async def one_round(
    planners: list[rc.Candidate], merger: rc.Candidate, number: int, folder: Path
) -> tuple[str, dict]:
    began = time.monotonic()
    texts = await asyncio.gather(
        *(rc._text(rc.Candidate(p.name, p.key, p.router), "planner", TASK) for p in planners)
    )
    plans = {p.name: t for p, t in zip(planners, texts, strict=True)}
    print(f"  round {number}: both plans in {time.monotonic() - began:.0f} s", flush=True)
    order = random.sample(list(plans), 2)  # what the merger sees as A and B: no names, random order
    request = ChatRequest(
        messages=[
            Message.system(MERGE_PROMPT),
            Message.user(f"TASK:\n{TASK}\n\nPLAN A:\n{plans[order[0]]}\n\nPLAN B:\n{plans[order[1]]}"),
        ]
    )
    answer = (await rc.Candidate(merger.name, merger.key, merger.router).ask(request, "judge")).text
    merged = parse_merge(answer)
    merged_text = report(merged) if merged else f"(the merge failed; its answer began: {answer[:300]})"
    print(f"  round {number}: merged in {time.monotonic() - began:.0f} s", flush=True)
    candidates = {**plans, f"merged by {merger.name}": merged_text}
    names = random.sample(list(candidates), 3)
    labels = [
        f"Plan {letter}{number}" for letter in random.sample(string.ascii_uppercase[23:26], 3)
    ]  # X, Y, Z
    labelled = dict(sorted(zip(labels, (candidates[n] for n in names), strict=True)))
    key = dict(zip(labels, names, strict=True))
    for label, text in labelled.items():
        (folder / f"{label.replace(' ', '_')}.md").write_text(text, encoding="utf-8")
    facts = {
        "key": key,
        "merge_order": {"A": order[0], "B": order[1]},
        "differences": [d.__dict__ for d in merged.differences] if merged else None,
        "words": {key[label]: len(text.split()) for label, text in labelled.items()},
    }
    return page(labelled, number), facts


async def main() -> int:
    parser = argparse.ArgumentParser(description="One planner or two: the plans side by side, unnamed.")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--key", action="store_true")
    args = parser.parse_args()
    base = forge_home() / "reports" / "plan-compare"
    if args.key:  # only after the judge has given its verdict: the judging is blind
        runs = sorted(base.glob("2*/key.json"))
        if not runs:
            print("No run yet.")
            return 1
        for n, fact in enumerate(json.loads(runs[-1].read_text(encoding="utf-8")), 1):
            print(f"Round {n}: " + ", ".join(f"{label} = {name}" for label, name in fact["key"].items()))
        return 0
    use_system_certificates()
    config, keys = rc.settings()
    router = LLMRouter(config, load_secrets(forge_home()))
    found = await rc.answering(router, keys, {*PLANNERS, MERGER})
    if any(name not in found for name in (*PLANNERS, MERGER)):
        print("Hydrogen and Argon must both answer. Photograph this screen and send it.")
        return 1
    folder = base / f"{datetime.now():%Y%m%d-%H%M}"
    folder.mkdir(parents=True, exist_ok=True)
    sections, facts = [], []
    for number in range(1, args.rounds + 1):
        section, fact = await one_round([found[n] for n in PLANNERS], found[MERGER], number, folder)
        sections.append(section)
        facts.append(fact)
    (folder / "key.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")
    (folder / "plans.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Plan compare</title>"
        "<style>body{font:15px/1.5 Segoe UI,sans-serif;max-width:900px;margin:24px auto;padding:0 16px}"
        "pre{white-space:pre-wrap;font:14px/1.5 Segoe UI,sans-serif;border-top:2px solid #2563eb;padding-top:8px}"
        "h3{margin-top:40px}</style>"
        f"<h1>Three plans for one task</h1><p>Photograph the whole page, top to bottom. The task is in "
        f"scripts/dev/plan_compare.py. Which plan is which is not shown.</p>{''.join(sections)}",
        encoding="utf-8",
    )
    print(f"\nThe page to photograph: {folder / 'plans.html'}")
    if sys.platform == "win32":
        os.startfile(folder / "plans.html")  # type: ignore[attr-defined]
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
