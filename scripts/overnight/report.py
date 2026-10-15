"""The morning report of the overnight run: one page that says what ran, what passed, what failed and which pictures to send back.

`write_report(out, state)` writes MORNING_REPORT.md and MORNING_REPORT.html (pictures included by relative path, so open the HTML from the run folder) after every job, so a partial night still has a report.
Everything that goes into the files is redacted first."""

from __future__ import annotations

import html
import re
import time
from pathlib import Path
from typing import Any

SCRUB = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)(\s*[:=]\s*)\S+")
try:  # the redaction DebCraft applies to everything it shows
    from forge.safety.redact import default_redactor
except Exception:  # run outside an installed DebCraft: only the plain scrub below
    default_redactor = None


def redact(text: str) -> str:
    """DebCraft's own redaction when it is importable, then a scrub of anything that looks like a key assignment."""
    if default_redactor is not None:
        text = default_redactor.redact(text)
    return SCRUB.sub(lambda match: match.group(1) + match.group(2) + "<hidden>", text)


BADGE = {
    "PASS": "#1a7f37",
    "PROBLEMS": "#b7791f",
    "FAILED": "#c53030",
    "TIMEOUT": "#c53030",
    "STALLED": "#c53030",
    "SKIPPED": "#6b7280",
    "RUNNING": "#2b6cb0",
    "PENDING": "#6b7280",
}


def minutes(seconds: float) -> str:
    seconds = int(seconds)
    return (
        f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"
        if seconds >= 3600
        else f"{seconds // 60}m {seconds % 60:02d}s"
    )


def counts(jobs: list[dict[str, Any]]) -> dict[str, int]:
    found: dict[str, int] = {}
    for job in jobs:
        found[job["status"]] = found.get(job["status"], 0) + 1
    return found


def what_to_send(job: dict[str, Any]) -> list[str]:
    files = [f"jobs/{job['id']}/failure.md" if job["status"] != "PASS" else ""]
    files += [f"jobs/{job['id']}/evidence/{name}" for name in job.get("evidence", [])[:6]]
    return [name for name in files if name]


def write_report(out: Path, state: dict[str, Any]) -> None:
    jobs: list[dict[str, Any]] = state["jobs"]
    summary = counts(jobs)
    started = state.get("started", "")
    lines = [
        "# Overnight run: morning report",
        "",
        f"Started {started}, last update {time.strftime('%Y-%m-%d %H:%M:%S')}. Commit: {state.get('commit', 'unknown')}. Profile: {state.get('profile', '')}.",
        f"Finished: {'yes' if state.get('finished') else 'NO, still running or stopped early (see the last job below)'}.",
        "",
        "**Totals:** "
        + ", ".join(f"{count} {name.lower()}" for name, count in sorted(summary.items()))
        + ".",
        "",
        "| # | Job | Result | Time | What it found |",
        "|---|---|---|---|---|",
    ]
    for index, job in enumerate(jobs, start=1):
        lines.append(
            f"| {index} | {job['title']} | **{job['status']}** | {minutes(job.get('seconds', 0)) if job.get('seconds') else ''} | {redact(str(job.get('finding', '')))[:200].replace('|', '/')} |"
        )
    failures = [job for job in jobs if job["status"] in ("FAILED", "PROBLEMS", "TIMEOUT", "STALLED")]
    lines += ["", "## What to send back", ""]
    if not failures:
        lines.append("Nothing failed. Send this report if you want it looked at.")
    else:
        lines.append(
            "For each item below, take a screenshot of the file named (open it in Notepad or the browser) and of the pictures listed, and send them back. Everything is relative to this folder."
        )
        lines.append("")
        for job in failures:
            lines += [f"### {job['title']} ({job['status']})", ""]
            lines += [f"- {name}" for name in what_to_send(job)]
            lines.append("")
    lines += ["## Environment", "", "```", redact(str(state.get("environment", ""))), "```", ""]
    text = "\n".join(lines)
    (out / "MORNING_REPORT.md").write_text(text, encoding="utf-8")
    (out / "MORNING_REPORT.html").write_text(render_html(out, state, summary, failures), encoding="utf-8")


def render_html(
    out: Path, state: dict[str, Any], summary: dict[str, int], failures: list[dict[str, Any]]
) -> str:
    def badge(status: str) -> str:
        return f'<span style="background:{BADGE.get(status, "#6b7280")};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">{html.escape(status)}</span>'

    rows = "".join(
        f"<tr><td>{index}</td><td>{html.escape(job['title'])}</td><td>{badge(job['status'])}</td><td>{html.escape(minutes(job.get('seconds', 0)) if job.get('seconds') else '')}</td>"
        f"<td>{html.escape(redact(str(job.get('finding', '')))[:240])}</td></tr>"
        for index, job in enumerate(state["jobs"], start=1)
    )
    sections = []
    for job in failures:
        folder = out / "jobs" / job["id"]
        failure = folder / "failure.md"
        body = (
            html.escape(redact(failure.read_text(encoding="utf-8", errors="replace")[:6000]))
            if failure.is_file()
            else ""
        )
        images = "".join(
            f'<figure><img src="jobs/{job["id"]}/evidence/{html.escape(name)}" style="max-width:480px;border:1px solid #ddd"><figcaption>{html.escape(name)}</figcaption></figure>'
            for name in job.get("evidence", [])
            if name.lower().endswith((".png", ".jpg", ".jpeg"))
        )
        sections.append(
            f"<h3>{html.escape(job['title'])} {badge(job['status'])}</h3><pre style='white-space:pre-wrap;background:#f6f8fa;padding:12px;font-size:12px'>{body}</pre><div style='display:flex;flex-wrap:wrap;gap:12px'>{images}</div>"
        )
    totals = ", ".join(f"{count} {html.escape(name.lower())}" for name, count in sorted(summary.items()))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Overnight run: morning report</title>"
        "<style>body{font-family:system-ui,Segoe UI,sans-serif;margin:24px;max-width:1200px;color:#1f2328}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #e5e7eb;padding:6px 10px;text-align:left;font-size:14px}h1{font-size:24px}</style></head><body>"
        f"<h1>Overnight run: morning report</h1><p>Started {html.escape(str(state.get('started', '')))}, last update {time.strftime('%Y-%m-%d %H:%M:%S')}. Finished: {'yes' if state.get('finished') else '<b>NO</b>, still running or stopped early'}.</p>"
        f"<p><b>Totals:</b> {totals}.</p><table><tr><th>#</th><th>Job</th><th>Result</th><th>Time</th><th>What it found</th></tr>{rows}</table>"
        f"<h2>What to send back</h2><p>Screenshot this page from the top, then the failure details below (scroll, one screenshot per section).</p>{''.join(sections) or '<p>Nothing failed.</p>'}"
        f"<h2>Environment</h2><pre style='font-size:12px'>{html.escape(redact(str(state.get('environment', ''))))}</pre></body></html>"
    )
