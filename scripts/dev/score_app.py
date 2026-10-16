"""Collect the evidence that the rubric of docs/APP_BENCHMARK.md is scored from: `python scripts/dev/score_app.py <run folder, e.g. C:\\Work\\ForgeRuns\\forge-apps\\hr_leave>`

Writes `<run folder>/evidence.md` and prints it: what DebCraft asked, the assumptions it recorded, its task list, the screens (templates and routes), the database tables and columns, the business rules found as data,
the roles it mentions, the tests (how many, what they check), the README's honesty part, and counts of words that signal 360-degree thinking (audit, delegate, escalat, tolerance, ...). It does not score:
the scoring is a judgement made from this file and from looking at the running application. Nothing is sent anywhere."""

from __future__ import annotations

import contextlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SIGNALS = {
    "audit trail": r"audit",
    "roles/permissions": r"role|permission|rbac|authori[sz]",
    "separation of duties": r"self[- ]approv|maker|checker|four[- ]eyes|segregation",
    "delegation": r"delegat",
    "escalation/SLA": r"escalat|sla\b|overdue|ageing|aging",
    "reason codes": r"reason[_ ]code|reason",
    "tolerance/limits": r"tolerance|threshold|limit",
    "rules as data/config": r"policy|rule[s_]|config|settings",
    "concurrency": r"concurren|optimistic|version|row[_ ]version|lock",
    "privacy/masking": r"mask|pii|redact|privacy|confidential",
    "import/export": r"import|export|csv|xlsx",
    "notifications": r"notif|reminder|email",
    "holiday/calendar": r"holiday|calendar",
    "cancel/withdraw/send back": r"withdraw|cancel|send[_ ]back|reopen",
    "pagination/search": r"paginat|page_size|search|filter",
    "empty states": r"empty[_ -]state|no .* yet|nothing to",
    "accessibility": r"aria-|role=\"|alt=",
    "currency/locale": r"currency|locale|timezone|time zone|iso",
}
SKIP = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache", "history.git", "egg-info"}


def files_of(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    found = []
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and path.suffix.lower() in suffixes
            and not (SKIP & set(part for part in path.parts))
        ) and not any(part.endswith(".egg-info") for part in path.parts):
            found.append(path)
    return found


def read(path: Path, limit: int = 400_000) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def events_of(workspace: Path) -> list[dict[str, Any]]:
    path = workspace / ".forge" / "transcripts" / "events.jsonl"
    out = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            with contextlib.suppress(ValueError):
                out.append(json.loads(line))
    return out


def section(title: str, lines: list[str]) -> list[str]:
    return ["", f"## {title}", "", *(lines or ["(none found)"])]


def evidence(run: Path) -> str:
    workspace = (
        run / "ws" if (run / "ws").is_dir() else run
    )  # a run folder of the benchmark, or a workspace itself
    project = workspace / "project"
    events = events_of(workspace)
    out = [f"# Evidence: {run.name}"]
    result = run / "result.json"
    if result.is_file():
        out += ["", "```", read(result), "```"]

    questions = [e for e in events if e["type"] == "question_asked"]
    out += section(
        f"Questions asked ({len(questions)})",
        [
            f"- {str(e['payload'].get('question') or e['payload'].get('text') or e['payload'])[:300]}"
            + (
                " | options: "
                + "; ".join(str(o.get("label", o))[:60] for o in (e["payload"].get("options") or [])[:4])
                if e["payload"].get("options")
                else ""
            )
            for e in questions
        ],
    )
    assumptions = [
        e["payload"].get("arguments", {})
        for e in events
        if e["type"] == "tool_call_started" and e["payload"].get("name") == "assumption_add"
    ]
    out += section(
        f"Assumptions recorded ({len(assumptions)})",
        [f"- {str(a.get('text') or a.get('assumption') or a)[:260]}" for a in assumptions],
    )
    tasks = []
    for e in events:
        if e["type"] == "task_list_updated" and e["payload"].get("tasks"):
            tasks = e["payload"]["tasks"]
    out += section(
        f"Final task list ({len(tasks)})",
        [f"- [{t.get('status', '')}] {str(t.get('title') or t.get('content') or t)[:200]}" for t in tasks],
    )

    code = files_of(project, (".py", ".html", ".js", ".css", ".sql", ".md", ".json", ".yaml", ".yml"))
    templates = [p for p in code if p.suffix == ".html"]
    out += section(
        f"Screens: templates ({len(templates)})", [f"- {p.relative_to(project)}" for p in templates[:80]]
    )
    routes: list[str] = []
    for path in [p for p in code if p.suffix == ".py"]:
        for method, route in re.findall(r"@\w+\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)", read(path)):
            routes.append(f"{method.upper():6} {route}")
    out += section(f"Routes ({len(routes)})", [f"- {r}" for r in sorted(set(routes))[:150]])

    tables: dict[str, list[str]] = {}
    for path in [p for p in code if p.suffix in (".py", ".sql")]:
        text = read(path)
        for name, body in re.findall(
            r"create table (?:if not exists )?[`\"']?(\w+)[`\"']?\s*\((.*?)\)\s*;", text, re.I | re.S
        ):
            tables[name] = [
                c.strip().split()[0]
                for c in body.split(",")
                if c.strip()
                and c.strip().split()[0].upper()
                not in {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"}
            ]
        for name, body in re.findall(r"__tablename__\s*=\s*[\"'](\w+)[\"'](.*?)(?=\nclass |\Z)", text, re.S):
            tables[name] = re.findall(r"^\s+(\w+)\s*(?::[^=\n]*)?=\s*(?:mapped_column|Column)", body, re.M)
    out += section(
        f"Database tables ({len(tables)})",
        [f"- **{name}** ({len(cols)}): {', '.join(cols[:40])}" for name, cols in sorted(tables.items())],
    )

    tests = [p for p in code if p.suffix == ".py" and "test" in p.name.lower()]
    count = sum(len(re.findall(r"^\s*(?:async )?def test_", read(p), re.M)) for p in tests)
    names = [n for p in tests for n in re.findall(r"^\s*(?:async )?def (test_\w+)", read(p), re.M)]
    out += section(f"Tests: {count} in {len(tests)} file(s)", [f"- {n}" for n in names[:80]])

    corpus = "\n".join(read(p) for p in code if "test" not in p.name.lower())
    counts = Counter({k: len(re.findall(v, corpus, re.I)) for k, v in SIGNALS.items()})
    out += section(
        "Signals in the code and pages (number of mentions; 0 means the idea is absent)",
        [f"- {k}: {v}" for k, v in sorted(counts.items(), key=lambda item: item[1])],
    )

    readmes = [
        p
        for p in code
        if p.name.lower() in ("readme.md", "assumptions.md", "design.md") or p.parent.name == "docs"
    ]
    out += section(
        "Documents", [f"- {p.relative_to(project)} ({len(read(p).split())} words)" for p in readmes]
    )
    for path in readmes:
        if path.name.lower() == "readme.md":
            text = read(path)
            out += ["", f"### {path.name} (first 3500 characters)", "", text[:3500]]
    seeds = [p for p in code if re.search(r"seed|sample|demo", p.name, re.I)]
    out += section("Seed/sample data files", [f"- {p.relative_to(project)}" for p in seeds[:20]])
    return "\n".join(out)


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    text = evidence(folder)
    (folder / "evidence.md").write_text(text, encoding="utf-8")
    print(text)
