"""`review_build` (D-671): why did what DebCraft built go wrong? A report in three layers, from the record, not from memory.

The user (2026-11-27): an agent DebCraft built produced wrong code again and again; DebCraft's correction loop fixed it,
but the question is why DebCraft built it that way. A model asked "why did you do that?" writes a plausible story after
the fact, so this tool never asks it that. The evidence is collected by code from the conversation's event log and
numbered (E1, E2, ...): the requests, the skills loaded, the plans, every failed step, the errors in outputs, the checks
that had to step in, the final content of the files written. The reviewer role's model (another model than the coder
where the user set it so) writes:

  Layer 1: what the built program did wrong, each point with its evidence;
  Layer 2: which decision of DebCraft caused or allowed it, each with its evidence; a claim whose evidence numbers do
           not exist in the record is marked unproven by the code;
  Layer 3: what to change in DebCraft (planner, prompts, skills, checks, tools), as proposals.

The report is a page under `<DebCraft Home>/reports/` that opens in its own browser tab; the user sends it to whoever
improves DebCraft. Secrets are masked; names are not, so the page says to read it before sending it anywhere."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.config import forge_home
from forge.errors import ConversationError, LLMError
from forge.llm.base import ChatRequest, Message
from forge.protocol.events import Event, EventType, load_event_log
from forge.safety.redact import default_redactor
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.workspace.conversations import ConversationStore

WRITING_TOOLS = frozenset({"write_file", "edit_file", "multi_edit", "apply_patch"})
RUNNING_TOOLS = frozenset(
    {"run_command", "python_run", "http_request", "read_background", "monitor", "browser_screenshot"}
)
ERROR_IN_OUTPUT = re.compile(
    r"Traceback|\bError\b|Exception|\bfailed\b|\"status\":\s*\"failed\"|tests_passed\"?:\s*false|exit code [1-9]|"
    r"\b[45]\d\d\b (?:Bad|Not|Internal|Unprocessable|Forbidden|Unauthorized)",
    re.IGNORECASE,
)
TEXT_CHARS = 700
FILE_CHARS = 9_000
FILES_CHARS = 70_000
MAX_EVIDENCE = 260
REPORTS = "reports"
RECENT_CONVERSATIONS = 3

PROMPT = """You review how DebCraft (an AI coding agent) built something that then went wrong, so that DebCraft itself can be
improved. You get the RECORD of the work: numbered pieces of evidence (E1, E2, ...) taken from DebCraft's own log, and
the final content of the files it wrote. Work ONLY from the record. You cannot know what DebCraft "thought"; you can
only see what it was asked, what it planned, what it wrote, what it ran and what failed.

Answer in three layers:

Layer 1, the built program's failures: what did the program DebCraft built (an agent, a service, a page) do wrong when it
ran? Quote the error each time. Keep apart a failure of the built program from a failure of DebCraft's own commands.

Layer 2, DebCraft's decisions: for each failure of layer 1, which decision or omission in DebCraft's work caused it or
let it through? Typical ones: requirements left vague; no specification of the output before the code; a system prompt
for the built agent without the rules it needed; how the input is interpreted left to the agent; no example or
reference; generated code that is believed instead of executed; the real execution environment (a playground, a test
run) used late or not as part of the generation; a validation loop that checks the wrong thing; a check that looks
plausible but was never run. Say what the record shows: "E14: the plan has no dashboard specification" is evidence;
"probably the model assumed" is not. When the record does not show the cause, say so and set "proven" to false.

Layer 3, changes to DebCraft: for each finding of layer 2, what should change in DebCraft so that the next program it
builds does not fail the same way: the planner, the prompts DebCraft writes for agents it builds, a skill, a check before
a task counts as done, a tool. Concrete and testable ("before generating the HTML, the built agent must produce a JSON
specification of the charts and the code must check each number against the CSV"), never "be more careful".

Answer with ONE JSON object and nothing else:
{"summary": "<two sentences>",
 "layer1": [{"failure": "...", "evidence": ["E7", "E9"]}],
 "layer2": [{"decision": "...", "caused": [1], "evidence": ["E3"], "proven": true}],
 "layer3": [{"change": "...", "part": "planner | prompt | skill | check | tool | other", "for": [1], "test": "how to see it works"}],
 "not_in_record": "what the record cannot show and would be needed"}
"caused" and "for" are numbers of items of the layer before (1 is the first)."""


def _clip(text: str, limit: int = TEXT_CHARS) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + " ..."


def collect(events: list[Event]) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """The numbered evidence and how often each file was changed. Code only: no model decides what is evidence."""
    evidence: list[str] = []
    changed: dict[str, int] = {}
    arguments: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event.payload
        kind = event.type
        if kind == EventType.USER_MESSAGE:
            evidence.append(f"the user asked: {_clip(payload.get('text', ''), 1500)}")
        elif kind == EventType.TOOL_CALL_STARTED:
            arguments[str(payload.get("id"))] = payload.get("arguments") or {}
        elif kind == EventType.TOOL_CALL_FINISHED:
            name = str(payload.get("name"))
            args = arguments.get(str(payload.get("id")), {})
            preview = str(payload.get("preview", ""))
            what = _clip(payload.get("summary") or name, 200)
            if name in WRITING_TOOLS:
                path = str(args.get("path") or args.get("file") or "")
                if path:
                    changed[path] = changed.get(path, 0) + 1
                if not payload.get("ok"):
                    evidence.append(f"{name} failed ({what}): {_clip(preview, 400)}")
            elif name == "load_skill" or name == "tool_search":
                evidence.append(f"{name}: {what}")
            elif name == "spawn_subagent":
                evidence.append(
                    f"subagent {_clip(args.get('agent', ''), 40)} reported: {_clip(preview, 2500)}"
                )
            elif name in ("todo_write", "task_update", "exit_plan_mode", "plan_write"):
                evidence.append(f"{name}: {_clip(json.dumps(args, ensure_ascii=False), 900)}")
            elif not payload.get("ok"):
                evidence.append(f"{name} failed ({what}): {_clip(preview)}")
            elif name in RUNNING_TOOLS and ERROR_IN_OUTPUT.search(preview):
                evidence.append(f"{name} ({what}) showed an error: {_clip(preview)}")
        elif kind == EventType.NOTICE and payload.get("kind") not in ("usage", "memory", "retry"):
            evidence.append(
                f"DebCraft's check stepped in ({payload.get('kind')}): {_clip(payload.get('text', ''), 300)}"
            )
        elif kind == EventType.MESSAGE_DONE and str(payload.get("text", "")).strip():
            evidence.append(f"DebCraft answered: {_clip(payload.get('text', ''), 900)}")
        elif kind == EventType.ERROR:
            evidence.append(f"error: {_clip(payload.get('message', ''), 400)}")
    if (
        len(evidence) > MAX_EVIDENCE
    ):  # the beginning (the request, the plan) and the end (the failures) matter most
        keep = MAX_EVIDENCE // 2
        evidence = [
            *evidence[:keep],
            f"({len(evidence) - 2 * keep} steps in between left out)",
            *evidence[-keep:],
        ]
    numbered = [(f"E{n}", default_redactor.redact(text)) for n, text in enumerate(evidence, 1)]
    return numbered, changed


def recent_conversations(store: ConversationStore, active: str) -> list[str]:
    """Without ids from the model: the RECENT_CONVERSATIONS latest earlier conversations that have a log (a live run called
    the tool with no arguments from a new conversation, and the review saw only its own investigation)."""
    found = [c.id for c in store.list() if c.id != active and store.events_path(c.id).is_file()]
    return found[-RECENT_CONVERSATIONS:]


def before_the_question(events: list[Event]) -> list[Event]:
    """The active conversation up to the user's question that asked for the review: what the model did after it, to
    look into the question, is not the work under review."""
    asks = [n for n, event in enumerate(events) if event.type == EventType.USER_MESSAGE]
    return events[: asks[-1]] if asks else events


def file_contents(root: Path, changed: dict[str, int]) -> list[tuple[str, int, str]]:
    """The final content of the files written, the most changed first, within FILES_CHARS."""
    out: list[tuple[str, int, str]] = []
    budget = FILES_CHARS
    for path, times in sorted(changed.items(), key=lambda item: -item[1]):
        file = root / path
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if budget <= 0:
            out.append((path, times, "(left out: the report's limit for file content was reached)"))
            continue
        shown = text[: min(FILE_CHARS, budget)]
        budget -= len(shown)
        out.append(
            (path, times, default_redactor.redact(shown) + ("\n... (cut)" if len(shown) < len(text) else ""))
        )
    return out


def parse(text: str) -> dict[str, Any] | None:
    found = re.search(r"\{.*\}", text, re.DOTALL)
    if found is None:
        return None
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("layer2"), list) else None


def check_evidence(review: dict[str, Any], known: set[str]) -> None:
    """A claim stands only on evidence that exists: unknown numbers are dropped, a layer-2 claim without any is unproven."""
    for layer in ("layer1", "layer2"):
        for item in review.get(layer) or []:
            if not isinstance(item, dict):
                continue
            cited = [str(e).strip() for e in item.get("evidence") or []]
            item["evidence"] = [e for e in cited if e in known]
            item["unknown"] = [e for e in cited if e not in known]
            if layer == "layer2" and not item["evidence"]:
                item["proven"] = False


def page(
    review: dict[str, Any], evidence: list[tuple[str, str]], files: list[tuple[str, int, str]], title: str
) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    def refs(item: dict[str, Any]) -> str:
        cited = " ".join(f'<a href="#{e}">{e}</a>' for e in item.get("evidence") or [])
        bad = (
            f" <span class=bad>(cited but not in the record: {esc(', '.join(item['unknown']))})</span>"
            if item.get("unknown")
            else ""
        )
        return f"<div class=refs>Evidence: {cited or '<span class=bad>none</span>'}{bad}</div>"

    parts = [f"<h1>{esc(title)}</h1>", f"<p class=summary>{esc(review.get('summary', ''))}</p>"]
    parts.append("<h2>Layer 1: what the built program did wrong</h2><ol>")
    parts += [
        f"<li>{esc(i.get('failure', ''))}{refs(i)}</li>"
        for i in review.get("layer1") or []
        if isinstance(i, dict)
    ]
    parts.append("</ol><h2>Layer 2: which decision of DebCraft caused or allowed it</h2><ol>")
    for item in (i for i in review.get("layer2") or [] if isinstance(i, dict)):
        mark = "" if item.get("proven") else " <span class=bad>UNPROVEN</span>"
        caused = ", ".join(f"failure {n}" for n in item.get("caused") or [])
        parts.append(
            f"<li>{esc(item.get('decision', ''))}{mark}<div class=refs>Led to: {esc(caused) or '-'}</div>{refs(item)}</li>"
        )
    parts.append("</ol><h2>Layer 3: what to change in DebCraft (proposals)</h2><ol>")
    for item in (i for i in review.get("layer3") or [] if isinstance(i, dict)):
        parts.append(
            f"<li><b>{esc(item.get('part', ''))}</b>: {esc(item.get('change', ''))}"
            f"<div class=refs>For finding {esc(', '.join(str(n) for n in item.get('for') or []))}. "
            f"Test: {esc(item.get('test', ''))}</div></li>"
        )
    parts.append(f"</ol><h2>What the record cannot show</h2><p>{esc(review.get('not_in_record', ''))}</p>")
    parts.append("<h2>The record</h2><ol class=record>")
    parts += [f'<li id="{n}"><b>{n}</b> {esc(text)}</li>' for n, text in evidence]
    parts.append("</ol><h2>Files written (final content)</h2>")
    parts += [f"<h3>{esc(path)} (changed {times}x)</h3><pre>{esc(text)}</pre>" for path, times, text in files]
    return (
        "<!doctype html><meta charset=utf-8><title>DebCraft build review</title>"
        "<style>body{font:15px/1.5 Segoe UI,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px}"
        "li{margin:8px 0}.refs{color:#4b5563;font-size:13px}.bad{color:#b91c1c;font-weight:600}"
        ".summary{font-size:16px}.warn{color:#b45309}.record li{font-size:13px}"
        "pre{white-space:pre-wrap;background:#f6f7f9;padding:8px;font-size:12px}</style>"
        "<p class=warn>Read this before you send it to anyone: keys and passwords are masked, but names, addresses and "
        "code are in it.</p>" + "".join(parts)
    )


def open_page(path: Path) -> None:
    if os.environ.get("FORGE_NO_BROWSER"):
        return
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            webbrowser.open(path.as_uri())
    except OSError:
        pass


class ReviewBuild(Tool):
    name = "review_build"
    read_only = True  # reads the log and the files; writes only the report into DebCraft Home
    description = (
        "When the user asks what went wrong in something DebCraft built, what mistakes DebCraft made, or why the "
        "generated code fails: a report in three layers (what the built program did wrong; which decision of "
        "DebCraft caused or allowed it; what to change in DebCraft), written by the reviewer model from the "
        "conversation's record with numbered evidence, opened in its own browser tab. Do not answer such a question "
        "from memory: call this. It reads this conversation and the recent earlier ones by itself; `conversations` "
        "(ids like c2) only when the user points at other ones."
    )

    class Args(ToolArgs):
        conversations: list[str] = Field(
            default_factory=list, description="Earlier conversation ids to include"
        )
        focus: str = Field(default="", description="What the user asked about, in their words")

    async def run(self, args: ReviewBuild.Args, context: ToolContext) -> ToolResult:
        store = ConversationStore(context.workspace)
        events: list[Event] = []
        try:
            active = store.active().id
            earlier = args.conversations or recent_conversations(store, active)
            for conversation in dict.fromkeys(earlier):
                log = store.events_path(conversation)
                if conversation != active and log.is_file():  # nothing happened yet in one without a log
                    events += load_event_log(log)
            log = store.events_path(active)
            if log.is_file():
                events += before_the_question(load_event_log(log))
        except ConversationError as error:
            return ToolResult(ok=False, content=str(error))
        evidence, changed = collect(events)
        if not evidence:
            return ToolResult(
                ok=False, content="The record is empty: nothing was built in these conversations."
            )
        files = file_contents(context.workspace.repo_dir, changed)
        record = "\n".join(f"{n}: {text}" for n, text in evidence)
        written = "\n\n".join(f"--- {path} (changed {times}x) ---\n{text}" for path, times, text in files)
        question = f"THE USER'S QUESTION: {args.focus or 'why did what DebCraft built go wrong?'}\n\nRECORD:\n{record}\n\nFILES WRITTEN:\n{written}"
        request = ChatRequest(messages=[Message.system(PROMPT), Message.user(question)])
        try:
            answer = (await context.ask_model("reviewer", request, "a review of how this was built")).text
        except LLMError as error:
            return ToolResult(ok=False, content=f"The reviewer model could not answer: {error}")
        review = parse(answer)
        if review is None:
            return ToolResult(
                ok=False, content="The reviewer model did not answer in the form asked for; call again."
            )
        check_evidence(review, {n for n, _ in evidence})
        folder = forge_home() / REPORTS
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"build-review-{datetime.now():%Y%m%d-%H%M%S}.html"
        title = f"Why the build went wrong: {context.workspace.root.name}"
        target.write_text(page(review, evidence, files, title), encoding="utf-8")
        open_page(target)
        await context.emit(
            "notice", {"kind": "build_review", "text": f"The build review opened in its own tab: {target}"}
        )
        unproven = sum(
            1 for item in review.get("layer2") or [] if isinstance(item, dict) and not item.get("proven")
        )
        headlines = "\n".join(
            f"- {item.get('decision', '')}{'' if item.get('proven') else ' (unproven)'}"
            for item in review.get("layer2") or []
            if isinstance(item, dict)
        )
        return ToolResult(
            ok=True,
            content=f"Report written and opened in the user's browser: {target}\n{len(evidence)} pieces of evidence, "
            f"{len(review.get('layer1') or [])} failures, {len(review.get('layer2') or [])} decisions ({unproven} unproven), "
            f"{len(review.get('layer3') or [])} proposed changes.\nLayer 2:\n{headlines}\nTell the user where the "
            "report is and give the layer-2 findings in a few lines; do not add causes the report does not show.",
            meta={
                "metrics": {
                    "evidence": len(evidence),
                    "decisions": len(review.get("layer2") or []),
                    "unproven": unproven,
                }
            },
        )
