"""The report of the role challenge: an HTML page in large type to print or scan, and the same table as text (D-655)."""

from __future__ import annotations

import html
from statistics import mean
from typing import Any

ROLES = {
    "planner": "Planner",
    "coder": "Coder",
    "reviewer": "Reviewer",
    "judge": "Judge",
    "critic": "Design critic",
    "vision": "Vision",
    "summariser": "Summariser",
    "fallback": "Fallback",
}
CLOSE = 8.0  # points: a smaller lead than this is not a difference
Row = dict[str, Any]


def _rows(rows: list[Row], role: str, model: str) -> list[Row]:
    return [r for r in rows if r["role"] == role and r["model"] == model]


def _scores(rows: list[Row], role: str, model: str) -> list[float]:
    """A failed call counts as 0: a role needs an answer. A wait for quota is not a failure."""
    return [float(r.get("score") or 0.0) for r in _rows(rows, role, model)]


def _seconds(rows: list[Row], role: str, model: str) -> float:
    values = [
        float(r["seconds"]) for r in _rows(rows, role, model) if r.get("seconds") and not r.get("error")
    ]
    return mean(values) if values else 0.0


def best(rows: list[Row], role: str, models: list[str]) -> list[tuple[str, float, float]]:
    """(model, mean score, mean seconds), the best first."""
    ranked = [
        (m, mean(scores), _seconds(rows, role, m)) for m in models if (scores := _scores(rows, role, m))
    ]
    return sorted(ranked, key=lambda entry: (-entry[1], entry[2]))


def verdict(rows: list[Row], role: str, models: list[str]) -> tuple[str, str, str]:
    """(choice, second, how sure). Among models too close to tell apart the fastest one is the choice."""
    ranked = best(rows, role, models)
    if not ranked:
        return "-", "-", "no result"
    top = ranked[0][1]
    spread = max(_scores(rows, role, ranked[0][0])) - min(_scores(rows, role, ranked[0][0]))
    margin = max(CLOSE, spread / 2)
    near = [entry for entry in ranked if top - entry[1] < margin]
    choice = min(near, key=lambda entry: entry[2] or 1e9)[0]
    others = [entry[0] for entry in ranked if entry[0] != choice]
    sure = "clear" if len(near) == 1 else f"close: {len(near)} models, the fastest is taken"
    return choice, others[0] if others else "-", sure


def text_table(rows: list[Row], models: list[str]) -> list[str]:
    out = [f"{'role':14} " + " ".join(f"{m[-13:]:>13}" for m in models) + "   choice"]
    for role, name in ROLES.items():
        cells = []
        for model in models:
            scores = _scores(rows, role, model)
            cells.append(f"{mean(scores):5.0f} {_seconds(rows, role, model):5.0f}s" if scores else "-")
        choice, _, sure = verdict(rows, role, models)
        out.append(f"{name:14} " + " ".join(f"{c:>13}" for c in cells) + f"   {choice} ({sure})")
    return out


STYLE = """
body{font:17px/1.4 'Segoe UI',Arial,sans-serif;color:#111;margin:24px;max-width:1080px}
h1{font-size:28px;margin:0 0 6px}h2{font-size:22px;margin:0 0 8px}
section{page-break-after:always;margin-bottom:40px}
table{border-collapse:collapse;width:100%;margin:10px 0 18px}
th,td{border:1px solid #777;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#e9edf4}td.n{text-align:center}td.best{background:#d7f0dd;font-weight:700}
small{color:#333;font-size:14px}.bad{color:#a11}
"""


def _cell(text: object, kind: str = "") -> str:
    return f'<td class="{kind}">{text}</td>' if kind else f"<td>{text}</td>"


def _table(head: list[str], body: list[list[str]]) -> str:
    return (
        "<table><tr>"
        + "".join(f"<th>{html.escape(h)}</th>" for h in head)
        + "</tr>"
        + "".join("<tr>" + "".join(row) + "</tr>" for row in body)
        + "</table>"
    )


def _overview(rows: list[Row], models: list[str], facts: dict[str, Any]) -> str:
    body = []
    for role, name in ROLES.items():
        choice, second, sure = verdict(rows, role, models)
        line = [_cell(f"<b>{name}</b>")]
        for model in models:
            scores = _scores(rows, role, model)
            if not scores:
                line.append(_cell("-", "n"))
                continue
            span = f"<br><small>{min(scores):.0f}-{max(scores):.0f}</small>" if len(scores) > 1 else ""
            line.append(_cell(f"{mean(scores):.0f}{span}", "n best" if model == choice else "n"))
        line += [_cell(html.escape(f"{choice}; then {second}")), _cell(f"<small>{html.escape(sure)}</small>")]
        body.append(line)
    return (
        "<section><h1>DebCraft role challenge</h1>"
        f"<p>{html.escape(facts.get('when', ''))}. Points from 0 to 100, the mean of the runs; below it the lowest and the "
        "highest run. The green model is the choice for the role.</p>"
        + _table(["Role", *models, "Choice", "How sure"], body)
        + f"<p><small>Less than {CLOSE:.0f} points apart (or within half the spread of the best model's own runs) counts as "
        "equal; then the faster model is the choice. A call that failed counts as 0.</small></p></section>"
    )


def _speed(rows: list[Row], models: list[str]) -> str:
    body = []
    for role, name in ROLES.items():
        body.append(
            [_cell(f"<b>{name}</b>")]
            + [_cell(f"{s:.0f} s" if (s := _seconds(rows, role, m)) else "-", "n") for m in models]
        )
    trouble = []
    for model in models:
        mine = [r for r in rows if r["model"] == model]
        errors = [r for r in mine if r.get("error")]
        waited = sum(float(r.get("waited") or 0) for r in mine)
        kinds = sorted({str(r["error"])[:140] for r in errors})
        trouble.append(
            [
                _cell(html.escape(model)),
                _cell(len(mine), "n"),
                _cell(len(errors), "n"),
                _cell(f"{waited:.0f} s", "n"),
                _cell(f"{sum(int(r.get('tokens') or 0) for r in mine):,}", "n"),
                _cell("<small>" + html.escape("; ".join(kinds[:3])) + "</small>"),
            ]
        )
    return (
        "<section><h2>Speed (mean seconds per task, waiting for quota not counted)</h2>"
        + _table(["Role", *models], body)
        + "<h2>Reliability</h2>"
        + _table(["Model", "tasks", "failed", "waited for quota", "tokens written", "errors"], trouble)
        + "</section>"
    )


def _details(rows: list[Row], models: list[str]) -> str:
    out = ["<section><h2>What happened, per role</h2>"]
    for role, name in ROLES.items():
        if role == "coder":
            continue
        body = []
        for model in models:
            mine = _rows(rows, role, model)
            if mine:
                notes = [
                    f"<b>{float(r.get('score') or 0):.0f}</b> {html.escape(str(r.get('error') or r.get('note') or ''))[:230]}"
                    for r in mine
                ]
                body.append([_cell(html.escape(model)), _cell("<small>" + "<br>".join(notes) + "</small>")])
        out.append(
            f"<h3>{name}</h3>" + _table(["Model", "points and what was right or wrong, per run"], body)
        )
    return "".join(out) + "</section>"


def _coder(rows: list[Row], models: list[str]) -> str:
    runs = [r for r in rows if r["role"] == "coder"]
    if not runs:
        return ""
    head = [
        "Model",
        "points",
        "questions",
        "reported fault, two relatives, old file",
        "build",
        "repair",
        "failed tool calls",
    ]
    body = []
    for model in models:
        for r in _rows(rows, "coder", model):
            if r.get("error"):
                body.append(
                    [
                        _cell(html.escape(model)),
                        _cell("0", "n"),
                        _cell(f'<span class="bad">{html.escape(str(r["error"]))[:200]}</span>'),
                    ]
                )
                continue
            camera = r.get("camera") or {}
            failed = r.get("failed_calls") or []
            body.append(
                [
                    _cell(html.escape(model)),
                    _cell(f"{float(r['score']):.0f}", "n"),
                    _cell(f"{r.get('right')} of {len(r['answers']['results'])}", "n"),
                    _cell(html.escape(", ".join(f"{k}: {'yes' if v else 'NO'}" for k, v in camera.items()))),
                    _cell(f"{r.get('build_seconds', 0) / 60:.1f} min", "n"),
                    _cell(f"{r.get('repair_seconds', 0) / 60:.1f} min", "n"),
                    _cell(f"{len(failed)}" + ("" if r.get("finished") else "<br>not finished"), "n"),
                ]
            )
    good = [r for r in runs if not r.get("error")]
    questions = list(good[0]["answers"]["results"]) if good else []
    detail = []
    for question in questions:
        line = [_cell(html.escape(question))]
        for r in good:
            result = r["answers"]["results"].get(question, {})
            line.append(
                _cell(
                    "ok"
                    if not result.get("problem")
                    else f'<span class="bad">{html.escape(result["problem"])}</span>',
                    "n",
                )
            )
        detail.append(line)
    heads = [f"{r['model']} {r['repeat'] + 1}" for r in good]
    return (
        "<section><h2>Coder: built and repaired by DebCraft with this model in every role</h2>"
        + _table(head, body)
        + "<h2>The unseen questions, run by run</h2>"
        + _table(["Question", *heads], detail)
        + "</section>"
    )


def page(rows: list[Row], models: list[str], facts: dict[str, Any]) -> str:
    notes = "".join(f"<li>{html.escape(str(n))}</li>" for n in facts.get("notes", []))
    return (
        f'<!doctype html><html lang="en"><meta charset="utf-8"><title>DebCraft role challenge</title><style>{STYLE}</style><body>'
        + _overview(rows, models, facts)
        + _speed(rows, models)
        + _coder(rows, models)
        + _details(rows, models)
        + f"<section><h2>How it was measured</h2><ul>{notes}</ul></section></body></html>"
    )
