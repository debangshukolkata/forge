"""C17: the scrubbed run report keeps what helps analysis and drops secrets, paths and source code."""

from __future__ import annotations

from pathlib import Path

from forge.engine.run_report import build_run_report, write_run_report
from forge.protocol.events import Event, EventType
from forge.safety.redact import Redactor


def _event(seq: int, kind: EventType, payload: dict[str, object]) -> Event:
    return Event(seq=seq, type=kind, ts=f"2026-10-13T10:00:{seq:02d}.000+00:00", payload=payload)


def _events(workspace: Path) -> list[Event]:
    return [
        _event(1, EventType.USER_MESSAGE, {"text": "build a page"}),
        _event(
            2,
            EventType.TOOL_CALL_FINISHED,
            {
                "name": "spawn_subagent",
                "ok": True,
                "summary": "design-critic",
                "preview": "hierarchy 4/5 clear\npolish 3/5 uneven\nVERDICT: REVISE",
                "duration_s": 3.0,
            },
        ),
        _event(
            3,
            EventType.TOOL_CALL_FINISHED,
            {
                "name": "run_command",
                "ok": False,
                "summary": "npm run build",
                "preview": rf"error in {workspace}\src\App.tsx key sk-secret-token-1234567890",
                "duration_s": 2.0,
            },
        ),
        _event(
            4,
            EventType.AGENT_FINISHED,
            {
                "id": "a1",
                "role": "design-critic",
                "ok": True,
                "tool_calls": 4,
                "failed_calls": 0,
                "duration_s": 30.0,
                "cost_usd": 0.12,
            },
        ),
        _event(
            5,
            EventType.TASK_LIST_UPDATED,
            {"tasks": [{"title": "Landing page", "status": "done", "attempts": 2}]},
        ),
    ]


def test_report_has_verdicts_agents_failures_and_tasks(tmp_path: Path) -> None:
    report = build_run_report(_events(tmp_path), tmp_path, Redactor())
    assert "REVISE" in report and "polish 3/5 uneven" in report
    assert "| design-critic | ok | 4 | 0 | 30.0s | $0.120 |" in report
    assert "run_command: npm run build" in report
    assert "[done] Landing page (attempts 2)" in report


def test_report_masks_secrets_and_local_folders(tmp_path: Path) -> None:
    redactor = Redactor()
    redactor.register("sk-secret-token-1234567890", "TEST_KEY")
    report = build_run_report(_events(tmp_path), tmp_path, redactor)
    assert "sk-secret-token-1234567890" not in report
    assert str(tmp_path) not in report
    assert "<workspace>" in report


def test_write_run_report_reads_the_workspace_log(tmp_path: Path) -> None:
    log = tmp_path / ".forge" / "transcripts" / "events.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("\n".join(e.model_dump_json() for e in _events(tmp_path)) + "\n", encoding="utf-8")
    target = write_run_report(tmp_path)
    assert target == tmp_path / ".forge" / "run-report.md"
    assert "Critic and reviewer verdicts" in target.read_text(encoding="utf-8")
