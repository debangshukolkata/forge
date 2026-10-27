"""Skill trigger evaluation and description tuning (TODO C14). Method and cost: docs/SKILL_TUNING.md.

    python scripts/benchmark/run_skill_triggers.py queries
    python scripts/benchmark/run_skill_triggers.py eval [--skills a,b] [--model ROLE] [--out DIR] [--repeat N] [--parallel 4]
    python scripts/benchmark/run_skill_triggers.py tune <skill> [--candidates 4] [--apply] [--model ROLE]

`eval` and `tune` call the model (about 240 short calls for all 12 skills); `queries` calls nothing. Nothing is written to a SKILL.md without `tune --apply`."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_trigger_lib as lib

REPO = lib.REPO
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "skilltriggers"
RECORD = REPO / "docs" / "SKILL_TUNING.md"
DEFAULT_ROLE = "judge"  # any role of the router; --model picks another
MAX_RETRIES = 6


def load_skills() -> dict[str, Any]:
    sys.path.insert(0, str(REPO / "src"))
    from forge.parity.skills import discover

    return discover()  # built-in skills only: the same set on every machine


def make_router(home: Path) -> Any:
    os.environ.setdefault("FORGE_ENV_FILE", str(REPO / ".env"))
    home.mkdir(parents=True, exist_ok=True)
    os.environ["FORGE_HOME"] = str(home)  # an own home: nothing of a DebCraft project is read or written
    sys.path.insert(0, str(REPO))
    from forge.config import load_config, load_secrets
    from tests.test_live_llm import router_for

    return router_for(load_config(), load_secrets())


def is_rate_limit(error: Exception) -> bool:
    return (
        getattr(error, "status_code", None) == 429
        or "429" in str(error)
        or "rate limit" in str(error).lower()
    )


class Asker:
    """One router, one event loop, one semaphore; a 429 is retried with growing waits."""

    def __init__(self, router: Any, role: str, parallel: int) -> None:
        self.router = router
        self.role = role
        self.gate = asyncio.Semaphore(max(parallel, 1))
        self.calls = 0

    async def chat(self, system: str, user: str) -> str:
        from forge.llm.base import ChatRequest, Message

        async with self.gate:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    self.calls += 1
                    response = await self.router.chat(
                        self.role,
                        ChatRequest(messages=[Message.system(system), Message(role="user", content=user)]),
                    )
                    return str(response.text)
                except Exception as error:
                    if not is_rate_limit(error) or attempt == MAX_RETRIES:
                        raise
                    wait = min(2 ** (attempt + 1), 60) + random.random()
                    print(f"[429] waiting {wait:.0f} s", flush=True)
                    await asyncio.sleep(wait)
        raise RuntimeError("unreachable")


async def choose(
    asker: Asker, skills: dict[str, Any], query: str, repeat: int
) -> tuple[str | None, list[str | None]]:
    system = lib.system_prompt(lib.build_index(skills))
    names = list(skills)
    raw = await asyncio.gather(*(asker.chat(system, lib.question(query)) for _ in range(repeat)))
    answers = [lib.parse_answer(text, names) for text in raw]
    return lib.majority(answers), answers


async def evaluate(
    asker: Asker, skills: dict[str, Any], cases: list[lib.Case], repeat: int
) -> list[tuple[lib.Case, str | None, list[str | None]]]:
    async def one(case: lib.Case) -> tuple[lib.Case, str | None, list[str | None]]:
        try:
            chosen, answers = await choose(asker, skills, case.query, repeat)
        except Exception as error:
            print(f"[error] {case.skill}: {type(error).__name__}: {str(error)[:120]}", flush=True)
            chosen, answers = None, []
        return case, chosen, answers

    return list(await asyncio.gather(*(one(c) for c in cases)))


def pairs(rows: list[tuple[lib.Case, str | None, list[str | None]]]) -> list[tuple[lib.Case, str | None]]:
    return [(case, chosen) for case, chosen, _ in rows]


# ---------- eval ----------


def eval_markdown(
    per_skill: dict[str, list[tuple[lib.Case, str | None, list[str | None]]]], repeat: int
) -> str:
    lines = [
        f"### Skill triggers ({datetime.now():%Y-%m-%d %H:%M}, {repeat} ask(s) per query)",
        "",
        "| Skill | Recall (should) | False triggers (should not) | Accuracy |",
        "|---|---|---|---|",
    ]
    details: list[str] = []
    for skill, rows in per_skill.items():
        score = lib.score_cases(pairs(rows))
        lines.append(
            f"| {skill} | {score.should_hit}/{score.should_total} | {score.not_false}/{score.not_total} | {score.accuracy:.0%} |"
        )
        counts = lib.confusions(pairs(rows))
        if score.missed or score.false_triggers:
            details += ["", f"#### {skill}"]
            if counts:
                details.append(
                    "Missed, chosen instead: " + ", ".join(f"{name} x{n}" for name, n in counts.most_common())
                )
            details += [f"- missed ({chosen or 'NONE'}): {query}" for query, chosen in score.missed]
            details += [f"- false trigger: {query}" for query in score.false_triggers]
    return "\n".join(lines + details) + "\n"


async def run_eval(args: argparse.Namespace) -> int:
    skills = load_skills()
    triggers = lib.load_triggers()
    wanted = [s for s in args.skills.split(",") if s] or list(triggers)
    unknown = [s for s in wanted if s not in triggers or s not in skills]
    if unknown:
        print(f"unknown skill(s): {', '.join(unknown)}", file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else RUNS / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    asker = Asker(make_router(out / "home"), args.model, args.parallel)
    per_skill: dict[str, list[tuple[lib.Case, str | None, list[str | None]]]] = {}
    for skill in wanted:
        print(f"[eval] {skill} ...", flush=True)
        per_skill[skill] = await evaluate(asker, skills, lib.cases_for(triggers, skill), args.repeat)
    report = eval_markdown(per_skill, args.repeat)
    (out / "results.json").write_text(
        json.dumps(
            {
                skill: [
                    {"kind": c.kind, "query": c.query, "chosen": chosen, "answers": answers}
                    for c, chosen, answers in rows
                ]
                for skill, rows in per_skill.items()
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    (out / "results.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"{asker.calls} model calls; written to {out}")
    return 0


# ---------- tune ----------


async def score_description(
    asker: Asker,
    skills: dict[str, Any],
    triggers: dict[str, dict[str, list[str]]],
    skill: str,
    description: str,
    repeat: int,
) -> tuple[lib.Score, lib.Score]:
    swapped = lib.swap_description(skills, skill, description)  # in memory only
    train, test = await asyncio.gather(
        evaluate(asker, swapped, lib.cases_for(triggers, skill, "train"), repeat),
        evaluate(asker, swapped, lib.cases_for(triggers, skill, "test"), repeat),
    )
    return lib.score_cases(pairs(train)), lib.score_cases(pairs(test))


def record_application(
    skill: str, old: str, new: str, train: lib.Score, test: lib.Score, old_scores: tuple[lib.Score, lib.Score]
) -> None:
    RECORD.parent.mkdir(exist_ok=True)
    existing = (
        RECORD.read_text(encoding="utf-8") if RECORD.exists() else "# Skill description tuning record\n"
    )
    line = (
        f"- {datetime.now():%Y-%m-%d} `{skill}`: train {lib.format_score(old_scores[0])} -> {lib.format_score(train)}; "
        f"test {lib.format_score(old_scores[1])} -> {lib.format_score(test)}.\n"
        f"  - old: {old}\n  - new: {new}\n"
    )
    RECORD.write_text(existing.rstrip() + "\n\n" + line, encoding="utf-8")


async def run_tune(args: argparse.Namespace) -> int:
    skills = load_skills()
    triggers = lib.load_triggers()
    skill = args.skill
    if skill not in triggers or skill not in skills:
        print(f"unknown skill: {skill}", file=sys.stderr)
        return 1
    out = RUNS / f"tune-{skill}-{datetime.now():%Y%m%d-%H%M%S}"
    asker = Asker(make_router(out / "home"), args.model, args.parallel)
    current = skills[skill].description
    print(f"[tune] current description: {current}", flush=True)
    cur_train, cur_test = await score_description(asker, skills, triggers, skill, current, args.repeat)
    print(
        f"[tune] current: train {lib.format_score(cur_train)} | test {lib.format_score(cur_test)}", flush=True
    )

    siblings = {n: s.description for n, s in skills.items() if n != skill}
    prompt = lib.rewrite_prompt(
        skill, current, [q for q, _ in cur_train.missed], cur_train.false_triggers, args.candidates, siblings
    )
    reply = await asker.chat(
        "You rewrite one-line skill descriptions so that a model loads the skill at the right moments.",
        prompt,
    )
    proposed = lib.parse_candidates(reply)[: args.candidates]
    candidates: list[tuple[str, lib.Score, lib.Score]] = []
    for description in proposed:
        problems = lib.description_problems(description)
        if problems:
            print(f"[tune] dropped ({'; '.join(problems)}): {description[:80]}", flush=True)
            continue
        train, test = await score_description(asker, skills, triggers, skill, description, args.repeat)
        candidates.append((description, train, test))

    lines = [
        f"### Tuning `{skill}` ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        "| # | Train | Test | Description |",
        "|---|---|---|---|",
        f"| current | {cur_train.accuracy:.0%} ({cur_train.should_hit}/{cur_train.should_total} hit, {cur_train.not_false}/{cur_train.not_total} false) "
        f"| {cur_test.accuracy:.0%} ({cur_test.should_hit}/{cur_test.should_total}, {cur_test.not_false}/{cur_test.not_total}) | {current} |",
    ]
    for index, (description, train, test) in enumerate(candidates, 1):
        lines.append(
            f"| {index} | {train.accuracy:.0%} ({train.should_hit}/{train.should_total}, {train.not_false}/{train.not_total}) "
            f"| {test.accuracy:.0%} ({test.should_hit}/{test.should_total}, {test.not_false}/{test.not_total}) | {description} |"
        )
    best, why = lib.recommend((cur_train, cur_test), candidates)
    lines += ["", f"Recommendation: {why}."]
    report = "\n".join(lines)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tune.md").write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"{asker.calls} model calls; written to {out}")

    if args.apply:
        if best is None:
            print("--apply: nothing to apply.")
            return 0
        description, train, test = candidates[best]
        path: Path = skills[skill].path
        text = path.read_text(encoding="utf-8", newline="")  # keep the line endings
        path.write_text(lib.set_description_in_text(text, description), encoding="utf-8", newline="")
        record_application(skill, current, description, train, test, (cur_train, cur_test))
        print(f"--apply: wrote candidate {best + 1} into {path} and a record into {RECORD}")
    elif best is not None:
        print("Not applied. Add --apply to write the recommended description into SKILL.md.")
    return 0


# ---------- queries ----------


def run_queries() -> int:
    triggers = lib.load_triggers()
    skills = load_skills()
    problems = lib.check_triggers(triggers, skills)
    total = 0
    for skill, groups in triggers.items():
        counts = {kind: len(groups.get(kind, [])) for kind in lib.KINDS}
        total += sum(counts.values())
        train = len(lib.cases_for(triggers, skill, "train"))
        print(
            f"{skill}: should {counts['should']}, should_not {counts['should_not']} (train {train}, test {sum(counts.values()) - train})"
        )
    print(f"{len(triggers)} skills, {total} queries; one eval asks {total} times per repeat")
    for problem in problems:
        print(f"PROBLEM {problem}")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("queries", help="count and check triggers.json (no model call)")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--model", default=DEFAULT_ROLE, help=f"router role that answers (default {DEFAULT_ROLE})"
        )
        p.add_argument("--parallel", type=int, default=4, help="calls at the same time")
        p.add_argument(
            "--repeat", type=int, default=1, help="ask each query N times; a trigger needs a majority"
        )

    e = sub.add_parser("eval", help="recall and false-trigger rate per skill")
    e.add_argument("--skills", default="", help="comma-separated skills (default all in triggers.json)")
    e.add_argument("--out", default="", help="output folder (default under the benchmark runs folder)")
    common(e)
    t = sub.add_parser("tune", help="propose, score and optionally apply a better description")
    t.add_argument("skill")
    t.add_argument("--candidates", type=int, default=4)
    t.add_argument(
        "--apply",
        action="store_true",
        help="write the recommended description into SKILL.md and docs/SKILL_TUNING.md",
    )
    common(t)
    args = parser.parse_args()
    if args.command == "queries":
        return run_queries()
    runner: Callable[[argparse.Namespace], Coroutine[Any, Any, int]] = (
        run_eval if args.command == "eval" else run_tune
    )
    return asyncio.run(runner(args))  # one event loop for every call: the router's HTTP clients belong to it


if __name__ == "__main__":
    sys.exit(main())
