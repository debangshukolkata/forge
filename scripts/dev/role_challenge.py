"""Which model for which role? The same challenge for Gemini and Azure models in all eight roles (D-655).

    .venv\\Scripts\\python scripts\\dev\\role_challenge.py --check     which models answer, and one try of every role (minutes)
    .venv\\Scripts\\python scripts\\dev\\role_challenge.py             the full run (hours, overnight; goes on where it stopped)
    ... --quick                 every role once
    ... --roles planner,coder   only these roles          ... --models gpt54,gemini-4-neon   only these models
    ... --new                   begin a new run instead of going on with the last one
    ... --report                only write the report of the last run again

It reads the keys the way DebCraft does and prints none. Everything is saved after each step in
<DebCraft Home>\\reports\\role-challenge\\<time>\\; report.html is the page to scan. Planner, reviewer, judge, critic,
vision, summariser and fallback are direct calls (3 times each); the coder works through DebCraft itself (2 times),
in a project made for the test, with a DebCraft Home of its own. No project, file, database or rule of the user is used."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))

from awake import keep_awake
from roles import coder, fallback, report, tasks

from forge.config import ForgeConfig, ModelConfig, forge_home, load_config, load_secrets
from forge.errors import ForgeError, LLMError, LLMRateLimitError
from forge.llm.base import ChatRequest, LLMResponse, Message
from forge.llm.router import LLMRouter
from forge.net import use_system_certificates

MODELS = ("gemini-4-carbon", "gemini-4-neon", "gemini-4-hydrogen", "gemini-4-argon", "gpt54", "gpt51")
DEFAULT = MODELS[
    :5
]  # gpt-5.1 is the model inside the coder's project and a stand-in grader; test it with --models
GRADERS = ("gpt54", "gemini-4-carbon", "gpt51", "gemini-4-argon")  # two of them, never the author of the plan
APP_MODELS = (
    "gpt51",
    "gpt54",
    "gemini-4-hydrogen",
)  # the first that answers is the model of the built application
CALL_TIMEOUT_S = 420
MAX_WAIT_S = 900
REPEATS = {"coder": 2}
PICTURES = Path(__file__).resolve().parent / "roles" / "pictures"
DIRECT = [role for role in report.ROLES if role != "coder"]


class Candidate:
    """One model: asks it the way DebCraft would for a role, and keeps what that took."""

    def __init__(self, name: str, key: str, router: LLMRouter) -> None:
        self.name, self.key, self.router = name, key, router
        self.waited = self.seconds = 0.0
        self.tokens = 0

    def reset(self) -> None:
        self.waited = self.seconds = 0.0
        self.tokens = 0

    async def ask(self, request: ChatRequest, role: str) -> LLMResponse:
        model = self.router.config.llm.models[self.key]
        effort = model.reasoning_effort
        if effort is not None:
            effort = self.router.config.llm.role_reasoning_effort.get(role, effort)
        request = request.model_copy(
            update={"reasoning_effort": effort, "max_output_tokens": model.max_output}
        )
        provider = self.router.provider(self.key)
        while True:
            began = time.perf_counter()
            try:
                response = await asyncio.wait_for(provider.chat(request), CALL_TIMEOUT_S)
            except LLMRateLimitError as error:
                delay = min(max(error.retry_after_s or 20.0, 5.0), 90.0)
                if self.waited + delay > MAX_WAIT_S:
                    raise
                self.waited += delay
                await asyncio.sleep(delay)
                continue
            self.seconds += time.perf_counter() - began
            self.tokens += response.usage.output_tokens
            return response


def picture(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode((PICTURES / f"{name}.png").read_bytes()).decode()


async def _text(candidate: Candidate, role: str, prompt: str, image: str | None = None) -> str:
    message = Message(role="user", content=prompt, images=[picture(image)] if image else [])
    return (await candidate.ask(ChatRequest(messages=[message]), role)).text


async def _pictures(
    candidate: Candidate,
    role: str,
    asked: dict[str, str],
    score: Callable[[str, str], tasks.Result],
) -> tuple[float, str, Any]:
    results, answers = [], {}
    for name, prompt in asked.items():
        answers[name] = await _text(candidate, role, prompt, name)
        results.append(score(name, answers[name]))
    return sum(r[0] for r in results) / len(results), " | ".join(r[1] for r in results), answers


async def _graded(candidate: Candidate, graders: list[Candidate]) -> tuple[float, str, Any]:
    plan = await _text(candidate, "planner", tasks.PLANNER)
    marks: dict[str, float] = {}
    for grader in graders:
        if grader.key == candidate.key or len(marks) == 2:
            continue
        try:
            mark = tasks.planner_score(await _text(grader, "judge", tasks.grader_prompt(plan)))
        except (LLMError, ForgeError, TimeoutError):
            continue
        if mark is not None:
            marks[grader.name] = mark
    if not marks:
        raise ForgeError("no grader answered")
    note = ", ".join(f"{name}: {mark:.0f}" for name, mark in marks.items())
    if len(marks) == 2 and abs(max(marks.values()) - min(marks.values())) > 20:
        note += " (the graders disagree)"
    return sum(marks.values()) / len(marks), note, plan


async def one_task(role: str, candidate: Candidate, graders: list[Candidate]) -> tuple[float, str, Any]:
    if role == "planner":
        return await _graded(candidate, graders)
    if role == "vision":
        return await _pictures(
            candidate, role, {n: p for n, (p, _) in tasks.VISION.items()}, tasks.vision_score
        )
    if role == "critic":
        return await _pictures(
            candidate, role, dict.fromkeys(tasks.CRITIC_FAULTS, tasks.CRITIC), tasks.critic_score
        )
    if role == "fallback":
        score, note = await fallback.play(lambda request: candidate.ask(request, "coder"), candidate.key)
        return score, note, None
    prompt, scored = {
        "reviewer": (tasks.REVIEWER, tasks.reviewer_score),
        "judge": (tasks.JUDGE, tasks.judge_score),
        "summariser": (tasks.SUMMARISER, tasks.summary_score),
    }[role]
    answer = await _text(candidate, role, prompt)
    return (*scored(answer), answer)


class Run:
    """The results of one run, saved after every step."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.file = folder / "results.json"
        folder.mkdir(parents=True, exist_ok=True)
        self.rows: list[dict[str, Any]] = []
        self.facts: dict[str, Any] = {}
        if self.file.is_file():
            data = json.loads(self.file.read_text(encoding="utf-8"))
            self.rows, self.facts = data["rows"], data["facts"]

    def done(self, role: str, model: str, repeat: int) -> bool:
        """A step that ended with an error is tried again when the run goes on."""
        return any(
            r["role"] == role and r["model"] == model and r["repeat"] == repeat and not r.get("error")
            for r in self.rows
        )

    def add(self, row: dict[str, Any]) -> None:
        same = ("role", "model", "repeat")
        self.rows = [r for r in self.rows if any(r[k] != row[k] for k in same)] + [row]
        self.save()

    def models(self) -> list[str]:
        names = {r["model"] for r in self.rows}
        return [m for m in MODELS if m in names]

    def save(self) -> None:
        part = self.file.with_suffix(".part")
        part.write_text(json.dumps({"facts": self.facts, "rows": self.rows}, indent=1), encoding="utf-8")
        part.replace(self.file)
        (self.folder / "report.html").write_text(
            report.page(self.rows, self.models(), self.facts), encoding="utf-8"
        )
        (self.folder / "report.txt").write_text(
            "\n".join(report.text_table(self.rows, self.models())), encoding="utf-8"
        )


def settings() -> tuple[ForgeConfig, dict[str, str]]:
    """The user's configuration with every candidate in it, and name -> config key."""
    config = load_config(forge_home())
    keys: dict[str, str] = {}
    for name in MODELS:
        if name in config.llm.models:
            keys[name] = name
            continue
        known = next((k for k, m in config.llm.models.items() if m.model_name == name), None)
        if known is None and name.startswith("gemini"):
            known = name.replace("-", "")
            config.llm.models[known] = ModelConfig(
                provider="gemini",
                label=name,
                model_name=name,
                context_window=1_000_000,
                max_output=32000,
                vision=True,
            )
        if known is not None:
            keys[name] = known
    return config, keys


def short(error: BaseException) -> str:
    return f"{type(error).__name__}: {' '.join(str(error).split())[:160]}"


async def answering(router: LLMRouter, keys: dict[str, str], wanted: set[str]) -> dict[str, Candidate]:
    print("\n== Which models answer here ==", flush=True)
    found: dict[str, Candidate] = {}
    for name, key in keys.items():
        if name not in wanted:
            continue
        candidate = Candidate(name, key, router)
        try:
            if not router._configured(key):
                raise ForgeError("not set up in the .env file")
            response = await candidate.ask(
                ChatRequest(messages=[Message.user("Reply with the word ready.")]), "coder"
            )
            found[name] = candidate
            print(f"  yes  {name:20} {candidate.seconds:5.1f} s  {response.served_model}", flush=True)
        except (LLMError, ForgeError, TimeoutError, ImportError) as error:
            print(f"  NO   {name:20} {short(error)}", flush=True)
    return found


async def direct(run: Run, role: str, candidate: Candidate, graders: list[Candidate], repeat: int) -> None:
    mine = Candidate(
        candidate.name, candidate.key, candidate.router
    )  # its own clock: models run side by side
    row: dict[str, Any] = {"role": role, "model": mine.name, "repeat": repeat}
    try:
        score, note, answer = await one_task(
            role, mine, [Candidate(g.name, g.key, g.router) for g in graders]
        )
        row |= {"score": round(score, 1), "note": note, "answer": answer}
    except Exception as error:  # one broken answer must not end a run of hours
        row |= {"score": 0.0, "error": short(error)}
    row |= {"seconds": round(mine.seconds, 1), "waited": round(mine.waited), "tokens": mine.tokens}
    run.add(row)
    print(
        f"  {datetime.now():%H:%M} {role:11} {mine.name:18} run {repeat + 1}: "
        + (f"ERROR {row['error']}" if row.get("error") else f"{row['score']:5.1f}  {row['note'][:90]}"),
        flush=True,
    )


async def direct_roles(
    run: Run, roles: list[str], chosen: list[Candidate], graders: list[Candidate], repeats: int
) -> None:
    """Models side by side, each one's tasks one after the other."""

    async def all_of(candidate: Candidate) -> None:
        for repeat in range(repeats):
            for role in roles:
                if not run.done(role, candidate.name, repeat):
                    await direct(run, role, candidate, graders, repeat)

    await asyncio.gather(*(all_of(c) for c in chosen))


async def coder_role(
    run: Run, config: ForgeConfig, chosen: list[Candidate], app: Candidate, repeats: int, folder: Path
) -> None:
    async def complete(prompt: str, as_json: bool) -> str:
        helper = Candidate(app.name, app.key, app.router)
        if as_json:
            prompt += "\n\nAnswer with one JSON object and nothing else."
        text = (await helper.ask(ChatRequest(messages=[Message.user(prompt)]), "summariser")).text.strip()
        if as_json:  # as a JSON mode would give it: without a code block around it
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return text

    server = coder.ModelServer(complete, asyncio.get_running_loop())
    try:
        for repeat in range(repeats):
            for candidate in chosen:
                if run.done("coder", candidate.name, repeat):
                    continue
                print(
                    f"  {datetime.now():%H:%M} coder       {candidate.name:18} run {repeat + 1}: working ...",
                    flush=True,
                )
                row: dict[str, Any] = {"role": "coder", "model": candidate.name, "repeat": repeat}
                try:
                    row |= await coder.run(
                        config,
                        load_secrets(forge_home()),
                        candidate.key,
                        folder / f"{candidate.name}-{repeat + 1}",
                        server.port,
                    )
                except Exception as error:
                    row |= {"score": 0.0, "error": short(error)}
                run.add(row)
                print(f"        {row.get('error') or row['note']}  ({row.get('score')})", flush=True)
    finally:
        server.close()


def latest(base: Path) -> Path | None:
    found = sorted(p for p in base.glob("*") if (p / "results.json").is_file())
    return found[-1] if found else None


def names(text: str, known: Any) -> list[str]:
    given = [t.strip() for t in text.split(",") if t.strip()]
    wrong = [t for t in given if t not in known]
    if wrong:
        raise SystemExit(f"Unknown: {', '.join(wrong)}. Known: {', '.join(known)}")
    return given


async def main() -> int:
    parser = argparse.ArgumentParser(description="The same challenge for every model in every role.")
    for flag in ("check", "quick", "new", "report"):
        parser.add_argument(f"--{flag}", action="store_true")
    parser.add_argument("--models", default="")
    parser.add_argument("--roles", default="")
    args = parser.parse_args()
    use_system_certificates()
    keep_awake()
    base = forge_home() / "reports" / "role-challenge"
    last = latest(base)
    if args.report:
        if last is None:
            print("There is no run yet.")
            return 1
        Run(last).save()
        print(last / "report.html")
        return 0
    config, keys = settings()
    router = LLMRouter(config, load_secrets(forge_home()))
    wanted = names(args.models, MODELS) or list(DEFAULT)
    roles = names(args.roles, report.ROLES) or list(report.ROLES)
    found = await answering(router, keys, {*wanted, *GRADERS, *APP_MODELS})
    chosen = [found[n] for n in wanted if n in found]
    graders = [found[n] for n in GRADERS if n in found]
    app = next((found[n] for n in APP_MODELS if n in found), None)
    if not chosen or app is None:
        print("No model answered; nothing to compare.")
        return 1
    stamp = f"{datetime.now():%Y%m%d-%H%M}"
    if args.check:
        run = Run(base / f"check-{stamp}" / "try")
        print("\n== One try of every role but the coder ==", flush=True)
        await direct_roles(run, [r for r in DIRECT if r in roles], chosen, graders, 1)
        broken = [r for r in run.rows if r.get("error")]
        print("\n" + "\n".join(report.text_table(run.rows, run.models())))
        print(
            f"\n{len(broken)} of {len(run.rows)} tries failed."
            + (" Send me a photo of this." if broken else " Ready.")
        )
        return 1 if broken else 0
    run = Run(base / stamp if args.new or last is None else last)
    print(f"\n== {'Going on with' if run.rows else 'New run in'} {run.folder} ==", flush=True)
    repeats = 1 if args.quick else 3
    run.facts = {
        "when": f"Begun {run.folder.name}, last step {datetime.now():%d %b %Y %H:%M}",
        "notes": [
            "Every model got the same texts and pictures; none of them was made for one model. "
            "Thinking effort as DebCraft sets it for the role.",
            f"Planner: {len(tasks.PLANNER_CHECKS)} yes/no criteria, graded without the author's name by two of "
            f"{', '.join(g.name for g in graders)}, never by the author.",
            "Reviewer: 13 planted defects and 4 correct functions that look wrong. Judge: 42 verdicts whose truth is known. "
            "Critic: 3 pages with 9 planted faults and one good page. Vision: 28 values in 8 pictures. "
            "Summariser: 20 facts in at most 130 words. Fallback: 8 checks on work another model began, with one mistake in it.",
            f"Coder: DebCraft with this model in every role and no other to fall back to; {len(coder.QUESTIONS)} questions "
            "it never saw (70 points), a reported fault with two relatives nobody mentioned (30 points). The built "
            f"application itself asks {app.name} for every candidate. At most {coder.BUILD_SECONDS // 60} minutes to build and "
            f"{coder.REPAIR_SECONDS // 60} to repair.",
            "Few runs: it shows large differences, not small ones.",
        ],
    }
    await direct_roles(run, [r for r in DIRECT if r in roles], chosen, graders, repeats)
    if "coder" in roles:
        runs = 1 if args.quick else REPEATS["coder"]
        await coder_role(run, config, chosen, app, runs, run.folder / "coder")
    run.facts["when"] = f"Begun {run.folder.name}, last step {datetime.now():%d %b %Y %H:%M}"
    run.save()
    print("\n" + "\n".join(report.text_table(run.rows, run.models())))
    print(f"\nThe report to scan: {run.folder / 'report.html'}")
    if sys.platform == "win32":
        os.startfile(run.folder / "report.html")  # type: ignore[attr-defined]
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
