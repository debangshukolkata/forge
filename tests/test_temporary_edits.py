"""Changes made only to investigate are recorded, kept in the copy and taken out of the delivery (WF2, D-622)."""

from __future__ import annotations

import json
from pathlib import Path

from forge.toolkit.base import ToolContext
from forge.tools.files import EditFile, MultiEdit, WriteFile
from forge.tools.temporary import TemporaryEditsTool
from forge.workspace.create import create_workspace
from forge.workspace.output import build_output
from forge.workspace.temporary_edits import TemporaryEdits, hunks_between
from tests.workspace_helpers import BOM_FILE, CRLF_FILE

SERVICE = "backend/claims_app/service_under_test.py"
SERVICE_TEXT = """import audit


def total(items):
    audit.record(items)
    amount = 0
    for item in items:
        amount += item
    return amount


def average(items):
    return total(items) / len(items)
"""


def context_for(original_repo: Path, tmp_path: Path) -> ToolContext:
    """A project on a small repository of its own that already holds SERVICE (so a change to it is a modification,
    not a new file), a CRLF file and a file with a byte-order mark. `original_repo` is shared and not copied."""
    repo = tmp_path / "repo"
    (repo / "backend/claims_app").mkdir(parents=True)
    (repo / SERVICE).write_text(SERVICE_TEXT, encoding="utf-8", newline="\n")
    (repo / CRLF_FILE).write_bytes(b'"""Old module."""\r\n\r\nVALUE = 1\r\n')
    (repo / BOM_FILE).write_bytes(b'\xef\xbb\xbf"""BOM module."""\nNAME = "claims"\n')
    return ToolContext(workspace=create_workspace(repo, tmp_path / "ws", "backend"), design_first=False)


def know(context: ToolContext, relative: str) -> str:
    """The file tools want a file read before it is changed."""
    path = context.workspace.repo_dir / relative
    context.reads.record(relative, path.read_bytes())
    return context.workspace.read_text(relative)[0]


async def edit(context: ToolContext, relative: str, old: str, new: str, **fields: str):  # type: ignore[no-untyped-def]
    know(context, relative)
    return await EditFile().run(
        EditFile.Args(path=relative, old_string=old, new_string=new, **fields), context
    )  # type: ignore[arg-type]


async def tool(context: ToolContext, **fields: object):  # type: ignore[no-untyped-def]
    return await TemporaryEditsTool().run(TemporaryEditsTool.Args(**fields), context)  # type: ignore[arg-type]


def delivered(context: ToolContext, relative: str) -> str | None:
    path = context.workspace.output_dir / relative
    return path.read_text(encoding="utf-8") if path.exists() else None


# --- the record -------------------------------------------------------------------------------------------------


def test_hunks_carry_their_context_and_are_taken_out_by_exact_match(
    original_repo: Path, tmp_path: Path
) -> None:
    edits = TemporaryEdits(create_workspace(original_repo, tmp_path / "ws", "backend"))
    before = "".join(f"line {number}\n" for number in range(1, 21))
    added = before.replace("line 5\n", "line 5\nprint('here')\n")
    replaced = added.replace("line 15\n", "# line 15\n")
    deleted = replaced.replace("line 19\n", "")

    assert [hunk["new"].count("print") for hunk in hunks_between(before, added)] == [1]
    assert len(hunks_between(before, deleted)) == 3  # one block per change: lines 5, 15 and 19
    edits.add("a.py", "logging", "trace", "edit", hunks_between(before, added))
    edits.add("a.py", "bypass", "skip 15 and 19", "edit", hunks_between(added, deleted))

    text, taken, left = edits.without("a.py", deleted)
    assert text == before and [entry["id"] for entry in taken] == [2, 1] and left == []

    # the lines of the second change were edited afterwards: it is reported, never guessed at
    later = deleted.replace("# line 15\n", "# line 15 (changed again)\n")
    text, taken, left = edits.without("a.py", later)
    assert [entry["id"] for entry in left] == [2] and [entry["id"] for entry in taken] == [1]
    assert "(changed again)" in text and "print('here')" not in text


def test_a_broken_record_file_reads_as_empty(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    (workspace.forge_dir / "temporary_edits.json").write_text("{not json", encoding="utf-8")
    assert TemporaryEdits(workspace).active() == []
    assert TemporaryEdits(workspace).add("a.py", "logging", "x", "create", []) == 1


# --- marking and the delivery -----------------------------------------------------------------------------------


async def test_a_logging_line_stays_in_the_copy_and_is_not_delivered(
    original_repo: Path, tmp_path: Path
) -> None:
    context = context_for(original_repo, tmp_path)
    result = await edit(
        context,
        SERVICE,
        "    amount = 0\n",
        "    amount = 0\n    print('items', items)\n",
        temporary="logging",
        reason="see what total receives",
    )
    assert result.ok and "temporary change #1 (logging)" in result.content
    assert "print('items', items)" in know(context, SERVICE)

    report = build_output(context.workspace)

    # the only change to the file was temporary: the file is not part of the delivery at all
    assert delivered(context, SERVICE) is None and SERVICE not in [change.path for change in report.files]
    changes_md = (context.workspace.output_dir / "CHANGES.md").read_text(encoding="utf-8")
    assert "## Temporary changes (not in these files)" in changes_md
    assert f"- logging, `{SERVICE}`: see what total receives." in changes_md
    assert "print('items'" not in (context.workspace.output_dir / "changes.patch").read_text(encoding="utf-8")


async def test_a_fix_is_delivered_without_the_bypass_beside_it(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    bypass = await edit(
        context,
        SERVICE,
        "    audit.record(items)\n",
        "    # audit.record(items)\n",
        temporary="bypass",
        reason="the audit service is not reachable here and is not the cause",
    )
    fix = await edit(
        context,
        SERVICE,
        "    return total(items) / len(items)\n",
        "    return total(items) / len(items) if items else 0\n",
        reason="An empty list no longer divides by zero",
    )
    assert bypass.ok and fix.ok and "temporary" not in fix.content

    report = build_output(context.workspace)

    text = delivered(context, SERVICE)
    assert text is not None and "    audit.record(items)\n" in text and "# audit.record" not in text
    assert "if items else 0" in text
    assert "# audit.record(items)" in know(context, SERVICE)  # the copy keeps it: the application still runs
    patch = (context.workspace.output_dir / "changes.patch").read_text(encoding="utf-8")
    assert "if items else 0" in patch and "audit" not in patch.replace("import audit", "")
    changes_md = (context.workspace.output_dir / "CHANGES.md").read_text(encoding="utf-8")
    assert "The solution was proved with this in place; what it bypasses was not exercised." in changes_md
    manifest = json.loads((context.workspace.output_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["temporary"] == [
        {
            "id": "1",
            "kind": "bypass",
            "path": SERVICE,
            "reason": "the audit service is not reachable here and is not the cause",
            "state": "active",
        }
    ]
    assert [change.temporary_left for change in report.files if change.path == SERVICE] == [[]]


async def test_a_project_without_temporary_changes_delivers_the_same_bytes_as_the_copy(
    original_repo: Path, tmp_path: Path
) -> None:
    context = context_for(original_repo, tmp_path)
    assert (await edit(context, SERVICE, "    amount = 0\n", "    amount = 0.0\n", reason="floats")).ok
    report = build_output(context.workspace)
    assert (context.workspace.output_dir / SERVICE).read_bytes() == (
        context.workspace.repo_dir / SERVICE
    ).read_bytes()
    assert report.temporary == []
    assert "Temporary changes" not in (context.workspace.output_dir / "CHANGES.md").read_text(
        encoding="utf-8"
    )


async def test_a_file_written_only_to_investigate_is_not_delivered_and_remove_deletes_it(
    original_repo: Path, tmp_path: Path
) -> None:
    context = context_for(original_repo, tmp_path)
    made = await WriteFile().run(
        WriteFile.Args(
            path="backend/audit_stub.py",
            content="def record(items):\n    return None\n",
            temporary="bypass",
            reason="stands in for the audit service",
        ),
        context,
    )
    assert made.ok and "temporary change #1" in made.content
    build_output(context.workspace)
    assert delivered(context, "backend/audit_stub.py") is None

    removed = await tool(context, action="remove")
    assert removed.ok and not (context.workspace.repo_dir / "backend/audit_stub.py").exists()
    assert TemporaryEdits(context.workspace).active() == []


async def test_a_temporary_change_needs_a_reason_a_repository_and_for_a_whole_file_a_new_one(
    original_repo: Path, tmp_path: Path
) -> None:
    context = context_for(original_repo, tmp_path)
    no_reason = await edit(context, SERVICE, "    amount = 0\n", "    amount = 1\n", temporary="bypass")
    assert not no_reason.ok and "needs `reason`" in no_reason.content
    know(context, SERVICE)
    whole = await WriteFile().run(
        WriteFile.Args(path=SERVICE, content="x = 1\n", temporary="logging", reason="r"), context
    )
    assert not whole.ok and "Use edit_file" in whole.content
    assert know(context, SERVICE) == SERVICE_TEXT and TemporaryEdits(context.workspace).entries() == []

    context.workspace.mode_b = True
    mode_b = await edit(
        context, SERVICE, "    amount = 0\n", "    amount = 1\n", temporary="bypass", reason="r"
    )
    assert not mode_b.ok and "existing repository" in mode_b.content


async def test_multi_edit_records_all_its_edits_as_one_change(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    know(context, SERVICE)
    result = await MultiEdit().run(
        MultiEdit.Args(
            path=SERVICE,
            edits=[
                MultiEdit.Args.Edit(old_string="    audit.record(items)\n", new_string="    pass\n"),
                MultiEdit.Args.Edit(
                    old_string="    return total(items) / len(items)\n",
                    new_string="    print(items)\n    return total(items) / len(items)\n",
                ),
            ],
            temporary="bypass",
            reason="audit off, and a look at the input",
        ),
        context,
    )
    assert result.ok and len(TemporaryEdits(context.workspace).active(SERVICE)) == 1
    build_output(context.workspace)
    assert delivered(context, SERVICE) is None  # both edits are out: nothing is left to deliver


# --- the tool ---------------------------------------------------------------------------------------------------


async def test_list_remove_and_mark(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    assert "No temporary changes" in (await tool(context)).content
    await edit(
        context,
        SERVICE,
        "    amount = 0\n",
        "    amount = 0\n    print(items)\n",
        temporary="logging",
        reason="trace",
    )
    listed = await tool(context, action="list")
    assert f"#1 logging {SERVICE}: trace (active)" in listed.content

    removed = await tool(context, action="remove", ids=[1])
    assert removed.ok and "Taken out: #1" in removed.content and "Run your check again" in removed.content
    assert know(context, SERVICE) == SERVICE_TEXT
    assert "(removed)" in (await tool(context, action="list")).content

    # a bypass made without marking it is recorded afterwards; the file is not touched by that
    await edit(
        context, SERVICE, "    audit.record(items)\n", "    pass  # audit off\n", reason="get it running"
    )
    before = know(context, SERVICE)
    twice = await tool(context, action="mark", path=SERVICE, text="    ", original="", reason="r")
    assert not twice.ok and "exactly once" in twice.content
    marked = await tool(
        context,
        action="mark",
        path=SERVICE,
        text="    pass  # audit off\n",
        original="    audit.record(items)\n",
        kind="bypass",
        reason="the audit service is not reachable here",
    )
    assert marked.ok and "#2" in marked.content and know(context, SERVICE) == before
    build_output(context.workspace)
    assert delivered(context, SERVICE) is None  # with the bypass out, the file equals the original


async def test_a_change_that_can_no_longer_be_taken_out_is_delivered_with_a_warning(
    original_repo: Path, tmp_path: Path
) -> None:
    context = context_for(original_repo, tmp_path)
    await edit(
        context,
        SERVICE,
        "    audit.record(items)\n",
        "    # audit.record(items)\n",
        temporary="bypass",
        reason="audit is not reachable",
    )
    await edit(
        context, SERVICE, "    # audit.record(items)\n", "    # audit.record(items)  # later\n", reason="x"
    )

    removed = await tool(context, action="remove")
    assert not removed.ok and "Not taken out" in removed.content and "by hand" in removed.content
    report = build_output(context.workspace)

    change = next(change for change in report.files if change.path == SERVICE)
    assert change.temporary_left == ["audit is not reachable"]
    assert "# later" in (delivered(context, SERVICE) or "")
    warning = "still holds a temporary change DebCraft could not take out: audit is not reachable"
    assert warning in (context.workspace.output_dir / "CHANGES.md").read_text(encoding="utf-8")
    assert warning in (context.workspace.output_dir / "COPY_INSTRUCTIONS.md").read_text(encoding="utf-8")


async def test_line_endings_and_a_byte_order_mark_survive(original_repo: Path, tmp_path: Path) -> None:
    context = context_for(original_repo, tmp_path)
    for relative, old, fix in (
        (CRLF_FILE, "VALUE = 1\n", "VALUE = 2\n"),
        (BOM_FILE, 'NAME = "claims"\n', 'NAME = "claim"\n'),
    ):
        text = know(context, relative)
        first_line = text.splitlines(keepends=True)[0]
        marked = await edit(
            context,
            relative,
            first_line,
            first_line + "print('loaded')\n",
            temporary="logging",
            reason="trace",
        )
        fixed = await edit(context, relative, old, fix, reason="the fix")
        assert marked.ok and fixed.ok, (marked.content, fixed.content)
    build_output(context.workspace)

    crlf = (context.workspace.output_dir / CRLF_FILE).read_bytes()
    assert crlf == b'"""Old module."""\r\n\r\nVALUE = 2\r\n'
    bom = (context.workspace.output_dir / BOM_FILE).read_bytes()
    assert bom == b'\xef\xbb\xbf"""BOM module."""\nNAME = "claim"\n'
    assert b"print('loaded')" in (context.workspace.repo_dir / CRLF_FILE).read_bytes()


# --- before the turn ends (the agent loop) ----------------------------------------------------------------------

BIG = "backend/big_module.py"
BIG_TEXT = "".join(f"def function_number_{n}():\n    return {n}\n" for n in range(60))
FINAL = "All done here."
REVIEW_MARK = "You check code changes before they are handed to the user"
FOUND = '{"leftovers": [{"path": "backend/big_module.py", "lines": "return 590", "why": "a fixed value"}]}'


async def run_turn(  # type: ignore[no-untyped-def]
    original_repo: Path, tmp_path: Path, steps: list[tuple[str, dict[str, object]]], review_answer: str
):
    """The mocked model makes the tool calls in `steps`, one per model call, then answers FINAL. A call of the
    reviewer (told apart by its instructions) is answered with `review_answer` and counted separately."""
    import asyncio

    import httpx2

    from forge.engine.session_host import SessionHost
    from forge.protocol.events import EventBus
    from forge.protocol.inputs import SendMessage
    from forge.safety.redact import Redactor
    from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output

    worked: list[int] = []
    reviews: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = request.content.decode("utf-8")
        if REVIEW_MARK in body:
            reviews.append(body)
            return reply(request, responses_body([text_output(review_answer)]))
        index = len(worked)
        worked.append(index)
        if index < len(steps):
            name, arguments = steps[index]
            return reply(
                request, responses_body([function_call_output(name, json.dumps(arguments), f"c{index}")])
            )
        return reply(request, responses_body([text_output(FINAL)]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.path_of(BIG).write_text(BIG_TEXT, encoding="utf-8")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    host.agent.context.require_baseline = False  # the first-edit test run (D-408) is not what is tested here
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Make function 59 return 590."))
    for _ in range(200):
        await asyncio.sleep(0.05)
        if host.history[-1].role == "assistant" and host.history[-1].content == FINAL:
            break
    await asyncio.sleep(1.0)  # a check after the first answer makes the model answer again
    runner.cancel()
    return host, reviews


def system_notes(host, start: str) -> list[str]:  # type: ignore[no-untyped-def]
    return [m.content for m in host.history if m.role == "system" and m.content.startswith(start)]


def an_edit(**extra: object) -> list[tuple[str, dict[str, object]]]:
    return [
        ("read_file", {"path": BIG}),
        ("edit_file", {"path": BIG, "old_string": "return 59", "new_string": "return 590", **extra}),
    ]


async def test_active_temporary_changes_are_named_once_before_the_turn_ends(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.tools.temporary import temporary_finish_note

    host, _ = await run_turn(
        original_repo, tmp_path, an_edit(temporary="bypass", reason="stands in for the real value"), "{}"
    )
    notes = system_notes(host, "Temporary changes are still in the copy")
    assert len(notes) == 1 and f"#1 bypass {BIG}: stands in for the real value" in notes[0]
    assert "Proved with <what> bypassed" in notes[0]
    assert temporary_finish_note(host.agent.context) == ""  # the same set is not named again in a later turn


async def test_an_unmarked_leftover_found_by_the_second_model_is_sent_back_once(
    original_repo: Path, tmp_path: Path
) -> None:
    host, reviews = await run_turn(original_repo, tmp_path, an_edit(), FOUND)
    notes = system_notes(host, "Before you finish: a second model read your changes")
    assert len(notes) == 1 and f"- {BIG}: return 590 (a fixed value)" in notes[0]
    assert "temporary_edits (action mark)" in notes[0]
    assert len(reviews) == 1 and "return 590" in reviews[0] and "Make function 59 return 590." in reviews[0]
    assert system_notes(host, "Temporary changes") == []


async def test_no_leftover_an_unreadable_answer_and_a_turn_without_changes_say_nothing(
    original_repo: Path, tmp_path: Path
) -> None:
    for number, answer in enumerate(('{"leftovers": []}', "I could not decide.")):
        host, reviews = await run_turn(original_repo, tmp_path / str(number), an_edit(), answer)
        assert len(reviews) == 1 and system_notes(host, "Before you finish") == []
    host, reviews = await run_turn(original_repo, tmp_path / "read", [("read_file", {"path": BIG})], FOUND)
    assert reviews == [] and system_notes(host, "Before you finish") == []  # nothing was changed in the turn


async def test_the_same_diff_is_not_read_twice_and_a_marked_change_is_not_in_it(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.tools.leftover_review import delivery_diff, review_leftovers

    host, reviews = await run_turn(original_repo, tmp_path, an_edit(), FOUND)
    context = host.agent.context
    assert await review_leftovers(context) is None and len(reviews) == 1  # unchanged since the last review

    workspace = context.workspace
    assert "return 590" in delivery_diff(workspace)
    marked = await tool(
        context,
        action="mark",
        path=BIG,
        text="    return 590\n",
        original="    return 59\n",
        reason="a stand-in",
    )
    assert marked.ok and "return 590" not in delivery_diff(workspace)
