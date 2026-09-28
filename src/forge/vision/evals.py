"""Eval sets and the eval runner (spec §13A.2-13A.4).

<repo>/evals/<name>/            (delivered with the code if the user wants)
  eval.yaml                     command: runs the BUILT system on one sample, prints prediction JSON
                                ({"fields": {...}, "regions": [{"label","page","box"}]}); {sample} is replaced
                                question_command (optional): prints the answer; {sample} and {question}
                                targets: {field_normalised: 0.9, region_recall: 0.8, max_seconds_per_sample: 20}
                                sensitive: true (default)   iou_threshold: 0.5
  samples/  labels/<stem>.json  questions.jsonl ({sample, question, expected, grading: exact|contains|judge})

run_eval writes .forge/reports/eval-<n>.md with per-sample results and overlays (expected = green,
predicted = red) in .forge/reports/eval-<n>/, appends to .forge/reports/eval-history.jsonl, and after
MAX_ROUNDS_BEFORE_DISCUSSION misses tells the agent to stop and discuss the gap with the user.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from forge.tools.base import ToolContext
from forge.tools.powershell import ps_quote
from forge.tools.shell import execute
from forge.vision.images import draw_boxes, open_image, save
from forge.vision.metrics import SampleScore, aggregate, check_targets, normalise, score_sample

MAX_ROUNDS_BEFORE_DISCUSSION = 3
SAMPLE_TIMEOUT_S = 180
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}
JUDGE_RUBRIC = """You grade one answer of a document question-answering system against the expected answer.
PASS if it states the same facts (wording may differ, units must match); FAIL if a fact is wrong, missing, or
the answer guesses where the expected answer says the information is unreadable. Reply 'PASS' or 'FAIL' on
the first line, then one short reason."""


@dataclass
class EvalSet:
    name: str
    root: Path
    config: dict[str, Any]

    @property
    def samples(self) -> list[Path]:
        folder = self.root / "samples"
        return (
            sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
            if folder.is_dir()
            else []
        )

    def label(self, sample: Path) -> dict[str, Any] | None:
        path = self.root / "labels" / f"{sample.stem}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def questions(self) -> list[dict[str, Any]]:
        path = self.root / "questions.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @property
    def sensitive(self) -> bool:
        return bool(self.config.get("sensitive", True))


def load_eval(context: ToolContext, name: str) -> EvalSet:
    root = (
        context.workspace.path_of(f"evals/{name}")
        if not context.workspace.info.app_subfolder
        else (context.workspace.path_of(f"{context.workspace.info.app_subfolder}/evals/{name}"))
    )
    if not root.is_dir():
        root = context.workspace.path_of(f"evals/{name}")
    config_path = root / "eval.yaml"
    if not config_path.exists():
        raise ValueError(
            f"No eval set {name!r}: expected {root}/eval.yaml (command, targets) with samples/ and labels/."
        )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not config.get("command") and not config.get("question_command"):
        raise ValueError("eval.yaml needs `command` (prediction JSON per sample) and/or `question_command`.")
    targets = config.get("targets") or {}
    wrong = {k: v for k, v in targets.items() if isinstance(v, bool) or not isinstance(v, int | float)}
    if not isinstance(targets, dict) or wrong:
        raise ValueError(
            f"eval.yaml `targets` must map metric names to numbers, e.g. field_normalised: 0.9, "
            f"region_recall: 0.9, mean_iou: 0.5, max_errors: 0 (got {wrong or targets!r})."
        )
    return EvalSet(name, root, config)


@dataclass
class EvalRun:
    number: int
    metrics: dict[str, float]
    misses: list[str]
    scores: list[SampleScore] = field(default_factory=list)
    report: Path | None = None
    round_in_a_row: int = 0

    def summary(self) -> str:
        lines = [f"Eval run {self.number}: " + ", ".join(f"{k}={v}" for k, v in self.metrics.items())]
        if self.misses:
            lines.append("Targets NOT met: " + "; ".join(self.misses))
        else:
            lines.append("All targets met.")
        worst = sorted(
            (s for s in self.scores if s.field_errors or s.error), key=lambda s: -len(s.field_errors)
        )[:5]
        for score in worst:
            detail = score.error or "; ".join(
                f"{p}: expected {e!r}, got {g!r}" for p, e, g in score.field_errors[:3]
            )
            lines.append(f"- {score.sample}: {detail}")
        if self.report is not None:
            lines.append(
                f"Report: {self.report.as_posix()} (overlays next to it; look at failing samples with view_image)"
            )
        if self.misses and self.round_in_a_row >= MAX_ROUNDS_BEFORE_DISCUSSION:
            lines.append(
                f"The targets were missed {self.round_in_a_row} runs in a row: STOP iterating and discuss with the user "
                "(ask_user) with options: lower the target, add more real labelled samples, use a document-intelligence "
                "service, or add human review for low-confidence fields."
            )
        return "\n".join(lines)


async def run_eval(context: ToolContext, name: str, subset: int | None = None, judge: Any = None) -> EvalRun:
    evalset = load_eval(context, name)
    samples = evalset.samples[: subset or None]
    targets = {k: float(v) for k, v in (evalset.config.get("targets") or {}).items()}
    reports = context.workspace.jail.check(context.workspace.forge_dir / "reports")
    reports.mkdir(parents=True, exist_ok=True)
    history_path = reports / "eval-history.jsonl"
    history = (
        [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
        if history_path.exists()
        else []
    )
    number = len(history) + 1
    overlay_dir = reports / f"eval-{number}"
    scores: list[SampleScore] = []
    seconds: list[float] = []
    for sample in samples:
        label = evalset.label(sample)
        if label is None or not evalset.config.get("command"):
            continue
        started = time.perf_counter()
        prediction, error = await _predict(context, evalset, sample)
        seconds.append(time.perf_counter() - started)
        score = score_sample(sample.name, label, prediction, float(evalset.config.get("iou_threshold", 0.5)))
        score.error = error
        scores.append(score)
        if label.get("regions") or prediction.get("regions"):
            _overlay(sample, label, prediction, overlay_dir)
    metrics: dict[str, float] = aggregate(scores) if scores else {"samples": 0.0}
    if seconds:
        metrics["seconds_per_sample"] = round(sum(seconds) / len(seconds), 2)
    answered = await _questions(context, evalset, subset, judge)
    if answered:
        metrics["answer_correct"] = round(sum(ok for ok, _ in answered) / len(answered), 4)
    metrics["synthetic_share"] = round(
        sum(1 for s in samples if (evalset.label(s) or {}).get("synthetic")) / max(len(samples), 1), 2
    )
    misses = check_targets(metrics, targets)
    streak = 0
    for entry in reversed([*history, {"name": name, "misses": misses}]):
        if entry.get("name") != name or not entry.get("misses"):
            break
        streak += 1
    run = EvalRun(number, metrics, misses, scores, reports / f"eval-{number}.md", streak)
    run.report.write_text(_report(evalset, run, targets, answered), encoding="utf-8")  # type: ignore[union-attr]
    with history_path.open("a", encoding="utf-8") as log:
        log.write(
            json.dumps({"n": number, "name": name, "metrics": metrics, "misses": misses, "ts": time.time()})
            + "\n"
        )
    return run


async def _predict(context: ToolContext, evalset: EvalSet, sample: Path) -> tuple[dict[str, Any], str]:
    command = str(evalset.config["command"]).replace("{sample}", ps_quote(str(sample)))
    python = context.shell.python if context.shell else None
    if python and command.startswith("python "):
        command = f"& {ps_quote(python)} " + command[len("python ") :]
    result = await execute(context, command, SAMPLE_TIMEOUT_S, context.workspace.info.app_subfolder or None)
    text = result.content
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return {}, "no JSON prediction in the output" if result.ok else f"command failed: {text[-300:]}"
    try:
        return json.loads(text[start : end + 1]), ""
    except json.JSONDecodeError as error:
        return {}, f"invalid prediction JSON: {error}"


async def _questions(
    context: ToolContext, evalset: EvalSet, subset: int | None, judge: Any
) -> list[tuple[bool, str]]:
    template = evalset.config.get("question_command")
    if not template:
        return []
    results = []
    for item in evalset.questions()[: subset or None]:
        sample = evalset.root / "samples" / item["sample"]
        command = (
            str(template)
            .replace("{sample}", ps_quote(str(sample)))
            .replace("{question}", ps_quote(item["question"]))
        )
        python = context.shell.python if context.shell else None
        if python and command.startswith("python "):
            command = f"& {ps_quote(python)} " + command[len("python ") :]
        result = await execute(
            context, command, SAMPLE_TIMEOUT_S, context.workspace.info.app_subfolder or None
        )
        answer = result.content.split("[exit code")[0].strip()
        grading = item.get("grading", "contains")
        expected = str(item.get("expected", ""))
        if grading == "exact":
            results.append((normalise(answer) == normalise(expected), answer))
        elif grading == "judge" and judge is not None:
            verdict = await judge(item["question"], expected, answer)
            results.append((verdict.upper().startswith("PASS"), answer))
        else:
            results.append((normalise(expected) in normalise(answer), answer))
    return results


def _overlay(sample: Path, label: dict[str, Any], prediction: dict[str, Any], folder: Path) -> None:
    if sample.suffix.lower() == ".pdf":
        return
    boxes = [
        {"box": r["box"], "label": f"expected {r.get('label')}", "colour": "#16a34a"}
        for r in label.get("regions", [])
    ]
    boxes += [
        {"box": r["box"], "label": f"predicted {r.get('label')}", "colour": "#e11d48"}
        for r in prediction.get("regions", [])
        if "box" in r
    ]
    save(draw_boxes(open_image(sample), boxes), folder / f"{sample.stem}.png")


def _report(
    evalset: EvalSet, run: EvalRun, targets: dict[str, float], answered: list[tuple[bool, str]]
) -> str:
    lines = [f"# Eval {run.number} — {evalset.name}", "", "| Metric | Value | Target |", "|---|---|---|"]
    lines += [
        f"| {k} | {v} | {targets.get(k, targets.get('max_' + k, ''))} |" for k, v in run.metrics.items()
    ]
    lines += [
        "",
        "**Targets met.**" if not run.misses else "**Targets not met:** " + "; ".join(run.misses),
        "",
    ]
    if run.metrics.get("synthetic_share", 0) > 0:
        lines.append(
            f"Note: {int(run.metrics['synthetic_share'] * 100)}% of the samples are synthetic — good for "
            "regressions, not proof of real-world accuracy."
        )
    lines += [
        "",
        "## Per sample",
        "",
        "| Sample | Fields ok | Regions (IoU) | Unreadable respected | Error |",
        "|---|---|---|---|---|",
    ]
    for s in run.scores:
        ious = ", ".join(f"{k} {v}" for k, v in s.region_ious.items()) or "-"
        lines.append(
            f"| {s.sample} | {s.fields_normalised}/{s.fields_total} | {ious} | {s.unreadable_respected}/{s.unreadable_total} | {s.error} |"
        )
    wrong = [(s.sample, p, e, g) for s in run.scores for p, e, g in s.field_errors]
    if wrong:
        lines += ["", "## Field errors", ""] + [
            f"- {sample} `{path}`: expected {e!r}, got {g!r}" for sample, path, e, g in wrong[:60]
        ]
    if answered:
        lines += ["", f"## Questions: {sum(ok for ok, _ in answered)}/{len(answered)} correct"]
    if evalset.sensitive:
        lines += [
            "",
            "Samples are marked sensitive: they went only to the configured enterprise model endpoint.",
        ]
    return "\n".join(lines) + "\n"
