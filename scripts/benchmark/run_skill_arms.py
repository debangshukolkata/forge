"""Skill arms experiment (TODO C16): DebCraft's own skills against the original Superpowers and mattpocock/skills.

    python scripts/benchmark/run_skill_arms.py <run-name> [--tasks t01_slugify,t11_rate_limiter] [--parallel 3] [--repeat 1]
        [--arms baseline,distilled,superpowers,mattpocock] [--superpowers-dir <folder>] [--mattpocock-dir <folder>]
        [--env KEY=VALUE ...] [--preflight-only] [--record]

Each arm is one run of run_code_benchmark.py on the same task list, one arm after the other (never two at once), named <run-name>-<arm>-<i>:
  baseline    every workflow skill switched off (FORGE_DISABLED_SKILLS); the domain skills that carry assets (python-project, ui-design-quality, ...) stay
  distilled   DebCraft as shipped
  superpowers the original obra/superpowers skills (FORGE_EXTRA_SKILLS_DIR), DebCraft's workflow skills switched off
  mattpocock  the mattpocock/skills set likewise
Nothing is downloaded here: install the external skills yourself (`forge skill add <link>`) and pass the folder that holds them
(a folder of <skill>/SKILL.md). An arm whose folder is not given is skipped with a printed reason."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import run_skill_ab as ab

from forge.parity.skills import _parse, discover

ARMS = ("baseline", "distilled", "superpowers", "mattpocock")
WORKFLOW_SKILLS = (
    "test-first",
    "debugging",
    "verify-before-done",
    "deep-modules",
    "solution-thinking",
    "parallel-builders",
    "pytest-patterns",
    "project-docs",
    "eval-harness",
)
# t01, t02, t04: one-function jobs that a heavy process should not slow down
TRIVIAL_TASKS = ("t01_slugify", "t02_durations", "t04_paginate_bug")


@dataclass
class Arm:
    name: str
    disabled: list[str] = field(default_factory=list)
    skills_dir: Path | None = None
    skip_reason: str = ""

    def env_pairs(self) -> list[str]:
        pairs = []
        if self.disabled:
            pairs.append(f"FORGE_DISABLED_SKILLS={','.join(self.disabled)}")
        if self.skills_dir is not None:
            pairs.append(f"FORGE_EXTRA_SKILLS_DIR={self.skills_dir}")
        return pairs


def folder_skills(folder: Path) -> set[str]:
    """The names of the skills a folder itself holds (without the built-in ones)."""
    names = set()
    for skill_file in sorted(folder.glob("*/SKILL.md")):
        skill = _parse(skill_file)
        if skill is not None:
            names.add(skill.name)
    return names


def build_arms(names: list[str], superpowers_dir: str = "", mattpocock_dir: str = "") -> list[Arm]:
    arms: list[Arm] = []
    for name in names:
        if name == "baseline":
            arms.append(Arm(name, disabled=list(WORKFLOW_SKILLS)))
        elif name == "distilled":
            arms.append(Arm(name))
        elif name in ("superpowers", "mattpocock"):
            given = superpowers_dir if name == "superpowers" else mattpocock_dir
            option = f"--{name}-dir"
            if not given:
                arms.append(Arm(name, skip_reason=f"{option} not given"))
                continue
            folder = Path(given)
            if not folder.is_dir() or not folder_skills(folder):
                arms.append(Arm(name, skip_reason=f"{option} {folder} has no <skill>/SKILL.md folders"))
                continue
            # A workflow skill is switched off, unless the external set brings a skill of the same name: that one replaces it.
            own = folder_skills(folder)
            arms.append(Arm(name, disabled=[s for s in WORKFLOW_SKILLS if s not in own], skills_dir=folder))
        else:
            arms.append(Arm(name, skip_reason=f"unknown arm (use {', '.join(ARMS)})"))
    return arms


@contextmanager
def patched_env(pairs: dict[str, str]) -> Iterator[None]:
    saved = {key: os.environ.get(key) for key in pairs}
    try:
        for key, value in pairs.items():
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)
        yield
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def visible_skills(arm: Arm, extra_env: list[str] | None = None) -> list[str]:
    """The skill names a run of this arm will see, computed by the real discover() with the arm's environment."""
    pairs = {"FORGE_DISABLED_SKILLS": "", "FORGE_EXTRA_SKILLS_DIR": ""}
    for pair in [*(extra_env or []), *arm.env_pairs()]:
        key, _, value = pair.partition("=")
        pairs[key] = value
    with patched_env(pairs):
        return sorted(discover())


def preflight(arms: list[Arm], extra_env: list[str] | None = None) -> str:
    lines = ["Pre-flight: skills each arm will see", ""]
    shipped = set(visible_skills(Arm("shipped")))
    for arm in arms:
        if arm.skip_reason:
            lines.append(f"- {arm.name}: SKIPPED ({arm.skip_reason})")
            continue
        seen = visible_skills(arm, extra_env)
        lines.append(f"- {arm.name}: {len(seen)} visible; disabled: {', '.join(arm.disabled) or 'none'}")
        lines.append(f"    visible: {', '.join(seen)}")
        if arm.skills_dir is not None:
            external = sorted(folder_skills(arm.skills_dir))
            lines.append(f"    external ({arm.skills_dir}): {', '.join(external)}")
            clashes = [n for n in external if n in shipped]
            if clashes:
                lines.append(
                    f"    note: these replace DebCraft skills of the same name: {', '.join(clashes)}"
                )
            setups = [n for n in external if "setup" in n.lower()]
            if setups:
                lines.append(
                    f"    WARNING: {', '.join(setups)} asks for a one-time setup per repository, which a benchmark run cannot answer; remove it from the arm's folder."
                )
    return "\n".join(lines)


def run_name(base: str, arm: str, index: int) -> str:
    return f"{base}-{arm}-{index}"


def trivial_wall(rows: list[dict[str, object]]) -> float:
    return float(sum(float(r.get("wall_s") or 0) for r in rows if str(r.get("id")) in TRIVIAL_TASKS))


def slowdown_note(results: dict[str, list[list[dict[str, object]]]]) -> str:
    """Wall time on the trivial tasks (t01, t02, t04) of each arm against baseline, averaged over repeats."""
    averages = {
        arm: sum(trivial_wall(rows) for rows in runs) / len(runs) for arm, runs in results.items() if runs
    }
    base = averages.get("baseline")
    if not base:
        return "Slow-down on trivial tasks: no baseline time for t01, t02 and t04 in this experiment."
    parts = [
        f"{arm} {wall:.0f} s ({(wall / base - 1) * 100:+.0f} percent)"
        for arm, wall in averages.items()
        if arm != "baseline"
    ]
    return (
        f"Slow-down on trivial tasks (t01, t02, t04 wall time; baseline {base:.0f} s): "
        + (", ".join(parts) or "no other arm")
        + ". A process that makes one-function jobs much slower is a cost even when the pass count is the same."
    )


def compare_arms(results: dict[str, list[list[dict[str, object]]]]) -> str:
    """results: arm -> one list of result rows per repeat."""
    lines = [
        "### Arms experiment",
        "",
        "| Arm | Run | Tasks passed | Hidden tests | Model calls | Wall s | Cost |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm, runs in results.items():
        for i, rows in enumerate(runs, 1):
            t = ab.totals(rows)
            lines.append(
                f"| {arm} | {i} | {int(t['tasks_passed'])}/{int(t['tasks'])} | {int(t['tests_passed'])}/{int(t['tests_total'])} | {int(t['calls'])} | {t['wall_s']:.0f} | ${t['cost_usd']:.2f} |"
            )
    arm_names = list(results)
    lines += ["", "Per task (hidden tests / wall s / calls; repeats separated by `;`):", ""]
    lines += ["| Task | " + " | ".join(arm_names) + " |", "|---|" + "---|" * len(arm_names)]
    ids: set[str] = {str(row.get("id")) for runs in results.values() for rows in runs for row in rows}
    for task in sorted(ids):
        cells = []
        for arm in arm_names:
            parts = []
            for rows in results[arm]:
                row = next((r for r in rows if str(r.get("id")) == task), {})
                parts.append(
                    f"{row.get('hidden_passed', '-')}/{row.get('hidden_total', '-')} / {row.get('wall_s', '-')} / {row.get('model_calls', '-')}"
                )
            cells.append("; ".join(parts))
        lines.append(f"| {task} | " + " | ".join(cells) + " |")
    lines += ["", slowdown_note(results)]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--tasks", default="")
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--superpowers-dir", default="")
    parser.add_argument("--mattpocock-dir", default="")
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--preflight-only", action="store_true", help="print the pre-flight listing and stop")
    parser.add_argument("--record", action="store_true", help="append the comparison to docs/SKILL_AB.md")
    args = parser.parse_args()
    arms = build_arms(
        [a.strip() for a in args.arms.split(",") if a.strip()], args.superpowers_dir, args.mattpocock_dir
    )
    print(preflight(arms, args.env), flush=True)
    if args.preflight_only:
        return 0
    results: dict[str, list[list[dict[str, object]]]] = {}
    for arm in arms:
        if arm.skip_reason:
            continue
        results[arm.name] = []
        for i in range(1, max(args.repeat, 1) + 1):
            rows = ab.run_condition(
                run_name(args.name, arm.name, i), args.tasks, args.parallel, [*args.env, *arm.env_pairs()]
            )
            results[arm.name].append(rows)
    if not results:
        print("No arm to run.")
        return 1
    report = compare_arms(results)
    print(report)
    if args.record:
        ab.RECORD.parent.mkdir(exist_ok=True)
        existing = (
            ab.RECORD.read_text(encoding="utf-8") if ab.RECORD.exists() else "# Skill A/B runs (C14, D-417)\n"
        )
        ab.RECORD.write_text(existing.rstrip() + "\n\n" + report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
