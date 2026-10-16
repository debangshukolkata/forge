"""Score the planning layer of benchmark runs against the reference scenarios of docs/APP_BENCHMARK.md:
`python scripts/dev/score_planning.py <label>=<folder holding hr_leave, bank_loan, supply_p2p> [<label>=<folder> ...]`

For each run it reads the text DebCraft produced before it began building (the planner's report, REQUIREMENTS.md, PLAN.md, the assumptions and the questions) and checks which reference scenarios of the domain appear there (a regular expression per scenario:
a crude but repeatable test of "did it think of this"), plus the generic habits of the solution-thinking skill (users with pains, observable acceptance criteria, a scope ledger with an Optional list, states, rules as data,
vertical slices, questions that matter). It prints a table. It does not replace reading the text: a scenario can be named and still be handled badly."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCENARIOS: dict[str, dict[str, str]] = {
    "hr_leave": {
        "pro-rata joiner/leaver": r"pro[- ]?rat|joiner|leaver|join date",
        "public holidays by location": r"holiday",
        "holiday/weekend inside a leave": r"weekend|holiday[- ]only|working days",
        "half-day": r"half[- ]day",
        "year-end / carry-over": r"carry[- ]?(over|forward)|year[- ]end|rollover",
        "negative balance / insufficient": r"insufficient|balance exhaust|negative balance|exhausted",
        "overlap by the same person": r"overlap",
        "team coverage / who else is away": r"who else|team absence|overlapping (team )?absence|availability",
        "blackout / notice period": r"blackout|notice[- ]period|lead[- ]time",
        "withdraw / cancel after approval": r"withdraw|cancel",
        "delegate / absent manager": r"delegat|absent manager|manager is (away|absent)|on holiday",
        "self-approval / skip-level": r"self[- ]approv|own leave|skip[- ]level",
        "escalation / timeout": r"escalat|timeout|time out|expire",
        "sick leave / medical": r"sick|medical",
        "payroll cut-off / export": r"payroll",
        "privacy of reasons": r"privacy|confidential|health",
        "concurrency": r"concurren",
        "audit of balance changes": r"audit",
        "rules as data / HR edits policy": r"without code|policy (screen|editor)|configurable|rule.*(data|table)",
        "part-time / work pattern": r"part[- ]time|work pattern",
        "import from Excel / migration": r"import|migrat|spreadsheet.*(load|seed)",
    },
    "bank_loan": {
        "duplicate applicant": r"duplicate",
        "KYC / documents checklist": r"kyc|document.*(check|verif)|checklist",
        "sanctions / PEP / AML": r"sanction|pep\b|aml|watch ?list",
        "income vs obligations / affordability": r"affordab|debt[- ]to[- ]income|dti|foir|obligation",
        "credit policy rules / score": r"score|policy rule|rule engine|rule[- ]set",
        "authority limit by amount": r"authority|limit",
        "maker-checker / no self-approval": r"maker|checker|four[- ]eyes|self[- ]approv|cannot approve (their|a case they)",
        "send back / return with comments": r"send back|return(ed)? (to|for)|clarification",
        "decline reason codes": r"reason code|decline reason|adverse",
        "withdrawal by applicant": r"withdraw",
        "offer / pricing / EMI": r"\bemi\b|instal+ment|pricing|rate band|apr\b|amorti",
        "offer expiry": r"expir|validity",
        "conditions precedent before disbursal": r"condition|only after approval|disburse.*(only|after)",
        "co-applicant / guarantor": r"co-?applicant|guarantor",
        "PII masking": r"mask|pii|redact|privacy",
        "immutable audit trail": r"audit",
        "SLA / ageing / turnaround": r"ageing|aging|turnaround|sla\b",
        "concurrency on the same case": r"concurren|optimistic|two (users|people)",
        "regulatory statement / disclosures": r"regulat|disclosure|key[- ]facts|cooling",
        "rules / products kept as data": r"rules? as data|configurable|rule[_ ]sets?|editable rule|product table",
        "integration seams (bureau, core)": r"bureau|core[- ]banking",
    },
    "plant_maintenance": {
        "asset register / hierarchy": r"asset|equipment (register|list)|machine (register|list)|hierarch",
        "asset criticality": r"critical",
        "preventive schedules (time or meter based)": r"preventive|pm|recurring|meter|running hours|interval",
        "work order types (breakdown, preventive, inspection)": r"breakdown|corrective|inspection",
        "priority and response targets": r"priority|sla|response time|target",
        "technician skills / shifts / assignment": r"skill|shift|assign|roster|certif",
        "safety / permit to work / lockout": r"lockout|loto|permit|safety",
        "spare parts stock and reservation": r"spare|parts|reserv|inventory",
        "reorder of critical spares": r"reorder|minimum stock|min stock|critical spare|stock-?out",
        "downtime recording with cause codes": r"downtime|cause code|failure code|failure cause|root cause",
        "MTBF / MTTR / availability": r"mtbf|mttr|availability|oee",
        "backlog and overdue PM": r"backlog|overdue",
        "approval for costly repairs": r"approval|approve|cost threshold|budget",
        "external contractor / vendor jobs": r"contractor|vendor|external",
        "shift handover notes": r"handover|hand-over|shift note",
        "completion checklist / sign-off": r"checklist|sign-?off|close(d)? out|completion",
        "repeat failure detection": r"repeat|recurring failure|chronic|bad actor",
        "cost tracking labour and parts": r"labou?r|cost",
        "warranty / service history": r"warranty|history|service record",
        "requests from operators (anyone can raise)": r"request|operator|raise",
        "audit trail": r"audit",
    },
    "supply_p2p": {
        "reorder point / safety stock": r"reorder|safety stock|re-order|stock[- ]out|run out",
        "two warehouses / per-warehouse stock": r"warehouse",
        "stock on hand / on order": r"on[- ]hand|on order|stock level|inventory",
        "unit-of-measure conversion": r"unit of measure|uom|pack size|case vs",
        "requisition approval by value": r"approval band|approval limit|threshold|by value|amount threshold",
        "PO amendment / revision": r"amend|revision|revis",
        "partial delivery / back-order": r"partial|back-?order|remaining quantity",
        "over/under-delivery tolerance": r"over-?(receipt|delivery)|under-?delivery|tolerance",
        "damaged / rejected goods": r"damag|reject(ed)? goods|quality",
        "batch / expiry": r"batch|lot\b|expiry|first[- ]expired",
        "three-way match": r"three-way|3-way|match",
        "price / quantity variance exceptions": r"variance|tolerance|mismatch",
        "duplicate supplier invoice": r"duplicate",
        "invoice without receipt / receipt without invoice": r"before receipt|without receipt|accrual|uninvoiced",
        "returns / debit note": r"return|debit note|credit note",
        "stock transfer between warehouses": r"transfer|in[- ]transit",
        "supplier master (terms, lead time, MOQ)": r"lead[- ]time|moq|minimum order|payment terms|supplier master",
        "late deliveries / OTIF": r"overdue|late deliver|otif|on[- ]time",
        "negative stock prevention": r"negative stock",
        "audit of price and quantity changes": r"audit",
        "multi-currency / tax": r"currency|tax",
    },
}

HABITS: dict[str, str] = {
    "users with pains (table or list)": r"hurts today|pain today|pain\b.*\|",
    "pain points traced to scope": r"pain point|traced|in scope (answer|response)",
    "observable acceptance criteria": r"acceptance criteria",
    "scope ledger": r"scope ledger",
    "Optional items listed, not built": r"optional",
    "left out on purpose + risk": r"risk of leaving out|left out on purpose|deliberately left out",
    "states / transitions named": r"states?:|workflow states|state machine|pending.*approved.*rejected",
    "rules kept as data": r"rules? as data|configurable|seeded policy|without code|editable",
    "vertical slices": r"vertical|slice",
    "domain expert additions": r"expert|practitioner|typically|industry standard",
}


def collect(run: Path) -> tuple[str, list[str]]:
    """(all planning text, the questions asked)."""
    workspace = run / "ws"
    parts: list[str] = []
    for name in ("REQUIREMENTS.md", "PLAN.md"):
        path = workspace / ".forge" / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    questions: list[str] = []
    events = workspace / ".forge" / "transcripts" / "events.jsonl"
    if events.is_file():
        for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event["type"] == "question_asked":
                questions.append(str(event["payload"].get("question", "")))
            if event["type"] == "tool_call_started" and event["payload"].get("name") == "assumption_add":
                parts.append(str((event["payload"].get("arguments") or {}).get("text", "")))
    longest = ""

    def walk(node: Any) -> None:
        nonlocal longest
        if isinstance(node, str):
            if (
                "[planner report]" in node
                or ("Objective and users" in node and "Acceptance" in node)
                or "1. Understanding" in node
            ) and len(node) > len(longest):
                longest = node
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in sorted((workspace / ".forge" / "transcripts" / "subagents").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                walk(json.loads(line))
            except ValueError:
                continue
    parts.append(longest)
    return "\n".join(parts), questions


def score(label: str, folder: Path) -> list[str]:
    rows = [f"### {label}"]
    for app, scenarios in SCENARIOS.items():
        run = folder / app
        if not (run / "ws").is_dir():
            continue
        text, questions = collect(run)
        low = text.lower()
        found = [name for name, pattern in scenarios.items() if re.search(pattern, low)]
        habits = [name for name, pattern in HABITS.items() if re.search(pattern, low)]
        missing = [name for name in scenarios if name not in found]
        rows.append(
            f"- **{app}**: scenarios {len(found)}/{len(scenarios)}; habits {len(habits)}/{len(HABITS)}; words {len(text.split())}; questions asked {len(questions)}"
        )
        rows.append(f"  - missing scenarios: {', '.join(missing) or 'none'}")
        rows.append(f"  - missing habits: {', '.join(h for h in HABITS if h not in habits) or 'none'}")
        rows.append(f"  - questions: {' | '.join(q[:90] for q in questions)}")
    return rows


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        label, _, path = argument.partition("=")
        print("\n".join(score(label, Path(path))))
        print()
