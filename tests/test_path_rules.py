"""D-297: rules that load only when a matching file is touched."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from forge.engine.session_host import SessionHost
from forge.parity.path_rules import PathRules, glob_to_regex, parse_rule
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage
from forge.safety.redact import Redactor
from forge.workspace.create import create_workspace
from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output


@pytest.mark.parametrize(
    "pattern,path,expected",
    [
        ("backend/**/*.py", "backend/claims_app/errors.py", True),
        ("backend/**/*.py", "backend/errors.py", True),
        ("backend/**/*.py", "frontend/app.py", False),
        ("*.sql", "db/migrations/001_init.sql", True),  # no slash: any folder
        ("*.sql", "db/migrations/001_init.sqlx", False),
        ("src/*.ts", "src/a.ts", True),
        ("src/*.ts", "src/deep/a.ts", False),  # one level only
        ("tests/**", "tests/unit/test_a.py", True),
        ("docs/?.md", "docs/a.md", True),
        ("docs/?.md", "docs/ab.md", False),
        ("Backend/*.PY", "backend/x.py", True),  # case does not matter on Windows paths
    ],
)
def test_globs(pattern: str, path: str, expected: bool) -> None:
    assert bool(glob_to_regex(pattern).match(path)) is expected


def test_rule_files_are_parsed_in_the_three_list_styles() -> None:
    flow = parse_rule("a", '---\npaths: ["backend/**/*.py", "*.sql"]\n---\nUse the helpers.')
    plain = parse_rule("b", "---\npaths: backend/**/*.py, *.sql\n---\nUse the helpers.")
    block = parse_rule("c", '---\npaths:\n  - "backend/**/*.py"\n  - *.sql\n---\nUse the helpers.')
    for rule in (flow, plain, block):
        assert (
            rule is not None
            and rule.patterns == ("backend/**/*.py", "*.sql")
            and rule.text == "Use the helpers."
        )
    assert parse_rule("none", "No front matter at all.") is None
    assert parse_rule("empty", "---\npaths: []\n---\nText") is None
    assert parse_rule("nobody", "---\npaths: [a]\n---\n") is None


def test_a_rule_is_delivered_once_for_the_first_matching_file(tmp_path: Path) -> None:
    folder = tmp_path / "rules"
    folder.mkdir()
    (folder / "db.md").write_text(
        '---\npaths: ["*.sql"]\n---\nNever write raw SQL in a route.', encoding="utf-8"
    )
    (folder / "ui.md").write_text("---\npaths: [web/**]\n---\nUse the design tokens.", encoding="utf-8")
    (folder / "always.md").write_text("Just text, no paths.", encoding="utf-8")
    rules = PathRules([folder, tmp_path / "missing"])
    assert [r.name for r in rules.rules()] == ["db", "ui"]
    assert rules.note_for("app/main.py") == ""
    first = rules.note_for("db/001.sql")
    assert "Rule 'db'" in first and "Never write raw SQL" in first and "db/001.sql" in first
    assert rules.note_for("db/002.sql") == ""  # already delivered
    assert "design tokens" in rules.note_for("web/app.tsx")


def test_long_rules_are_capped(tmp_path: Path) -> None:
    folder = tmp_path / "rules"
    folder.mkdir()
    (folder / "long.md").write_text("---\npaths: [a.py]\n---\n" + "word " * 5000, encoding="utf-8")
    note = PathRules([folder]).note_for("a.py")
    assert "tokens omitted" in note and len(note) < 6000


async def test_the_rule_reaches_the_model_with_the_result_of_the_file_it_read(
    original_repo: Path, tmp_path: Path
) -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return reply(
                request,
                responses_body(
                    [function_call_output("read_file", '{"path": "backend/claims_app/errors.py"}')]
                ),
            )
        return reply(request, responses_body([text_output("done")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    rules = workspace.forge_dir / "rules"
    rules.mkdir(parents=True)
    (rules / "errors.md").write_text(
        '---\npaths: ["backend/**/errors.py"]\n---\nSubclass ClaimsAppError for every new error.',
        encoding="utf-8",
    )
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Read the errors module."))
    for _ in range(200):
        await asyncio.sleep(0.05)
        if any(e.type == EventType.COST_UPDATED for e in host.bus.events_since(0)):
            break
    runner.cancel()

    assert len(bodies) >= 2
    sent = json.dumps(bodies[1])
    assert "Rules that apply to backend/claims_app/errors.py" in sent and "Subclass ClaimsAppError" in sent
