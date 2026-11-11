"""Topic notes, the live-folder refresh and /learn (KL2, KL3, D-566)."""

# ruff: noqa: F811  (the `shop` fixture is imported from another test module)

from __future__ import annotations

from pathlib import Path

from forge.knowledge.code_map import CodeMap
from forge.knowledge.structure import load
from forge.knowledge.topics import MAX_BODY_CHARS, all_topics
from forge.parity.skills import discover
from forge.toolkit.base import ToolContext, ToolResult
from forge.tools.code_map_tool import CodeMapTool, knowledge_store, repository_map_pin
from forge.tools.knowledge_tools import (
    READS_BEFORE_REMINDER,
    READS_BEFORE_WRITE_REMINDER,
    KnowledgeSearch,
    KnowledgeWrite,
    learn_request,
    learning_status,
    reading_note,
)
from forge.tools.registry import default_tools, session_tools
from forge.workspace.create import create_workspace
from tests.test_knowledge_structure import SECURITY, shop  # noqa: F401  (shop is a fixture)

BODY = (
    "A request is authenticated by `current_user` (shop/security.py:5), which calls `_decode` "
    "(shop/security.py:9). `_decode` reads the setting SHOP_JWT_SECRET. Endpoints ask for it with "
    "`Depends(current_user)` (shop/main.py:19)."
)


async def _write(context: ToolContext, **fields: object) -> ToolResult:
    return await KnowledgeWrite().run(KnowledgeWrite.Args(**fields), context)  # type: ignore[arg-type]


async def _search(context: ToolContext, action: str, query: str = "") -> ToolResult:
    return await KnowledgeSearch().run(KnowledgeSearch.Args(action=action, query=query), context)  # type: ignore[arg-type]


async def _auth_topic(context: ToolContext) -> ToolResult:
    return await _write(
        context,
        title="How a request is authenticated",
        summary="Which function checks the token and which setting holds the secret",
        body=BODY,
        sources=["shop/security.py", "shop/main.py"],
    )


async def test_the_index_follows_the_users_folder_and_a_project_is_answered_for_its_own_copy(
    isolated_forge_home: Path,
    shop: Path,
    tmp_path: Path,
) -> None:
    first = create_workspace(shop, tmp_path / "ws1", "")
    assert "Map of this repository" in (repository_map_pin(first) or "")
    store = knowledge_store(first)
    assert "last_changes" not in load(store)  # the first build is not "a change"

    # A colleague changes the repository after the project was created.
    (shop / "shop" / "security.py").write_text(
        SECURITY + "\n\ndef added_by_a_colleague() -> None: ...\n", encoding="utf-8"
    )
    pin = repository_map_pin(first) or ""
    assert "Changed in the repository when the map was last updated" in pin and "shop/security.py" in pin
    assert CodeMap(load(store)).named("added_by_a_colleague")  # the stored index knows the new function

    found = await CodeMapTool().run(
        CodeMapTool.Args(action="find", query="added_by_a_colleague"), ToolContext(workspace=first)
    )
    assert (
        "Nothing found" in found.content
    )  # this project's copy does not have it: answers match what it edits
    assert CodeMap(load(store)).named("added_by_a_colleague")  # and answering did not push the index back

    second = create_workspace(shop, tmp_path / "ws2", "")
    newer = await CodeMapTool().run(
        CodeMapTool.Args(action="find", query="added_by_a_colleague"), ToolContext(workspace=second)
    )
    assert "shop/security.py" in newer.content


async def test_a_topic_written_in_one_project_is_there_in_the_next(
    isolated_forge_home: Path, shop: Path, tmp_path: Path
) -> None:
    first = ToolContext(workspace=create_workspace(shop, tmp_path / "ws1", ""))
    pinned: dict[str, str | None] = {}
    first.pin = pinned.__setitem__
    written = await _auth_topic(first)
    assert written.ok and "2 source files tracked" in written.content and first.knowledge_written
    store = knowledge_store(first.workspace)
    assert (store / "topics" / "how-a-request-is-authenticated.md").is_file()
    assert str(store).startswith(str(isolated_forge_home)) and not list(shop.rglob("topics"))
    assert "how-a-request-is-authenticated: How a request is authenticated" in (pinned["kb_essentials"] or "")

    second = ToolContext(workspace=create_workspace(shop, tmp_path / "ws2", ""))
    assert "how-a-request-is-authenticated" in (repository_map_pin(second.workspace) or "")
    found = await _search(second, "search", "token secret")
    assert (
        found.ok and "how-a-request-is-authenticated" in found.content and "SHOP_JWT_SECRET" in found.content
    )
    read = await _search(second, "read", "how-a-request-is-authenticated")
    assert read.ok and BODY in read.content and "- shop/security.py" in read.content
    assert "changed since this topic was written" not in read.content and second.knowledge_looked
    nothing = await _search(second, "search", "kubernetes helm")
    assert nothing.ok and "Nothing written down matches" in nothing.content


async def test_a_topic_whose_files_changed_is_flagged_then_confirmed_or_corrected(
    isolated_forge_home: Path,
    shop: Path,
    tmp_path: Path,
) -> None:
    first = ToolContext(workspace=create_workspace(shop, tmp_path / "ws1", ""))
    await _auth_topic(first)
    (shop / "shop" / "security.py").write_text(
        SECURITY.replace("SHOP_JWT_SECRET", "SHOP_SIGNING_KEY"), encoding="utf-8"
    )

    later = ToolContext(workspace=create_workspace(shop, tmp_path / "ws2", ""))
    assert "[may be outdated: 1 of its files changed]" in (repository_map_pin(later.workspace) or "")
    read = await _search(later, "read", "how-a-request-is-authenticated")
    assert (
        "These source files changed since this topic was written" in read.content
        and "shop/security.py" in read.content
    )
    agenda = await _search(later, "agenda")
    assert (
        "Topics to re-check" in agenda.content
        and "how-a-request-is-authenticated: shop/security.py" in agenda.content
    )

    corrected = await _write(
        later,
        slug="how-a-request-is-authenticated",
        summary="Which function checks the token and which setting holds the secret",
        body=BODY.replace("SHOP_JWT_SECRET", "SHOP_SIGNING_KEY"),
        sources=["shop/security.py", "shop/main.py"],
        reason="the setting was renamed from SHOP_JWT_SECRET to SHOP_SIGNING_KEY",
    )
    assert corrected.ok and "corrected" in corrected.content
    again = await _search(later, "read", "how-a-request-is-authenticated")
    assert "SHOP_SIGNING_KEY" in again.content and "changed since this topic" not in again.content
    assert "Corrections so far" in again.content and "renamed from SHOP_JWT_SECRET" in again.content
    assert again.content.startswith("# How a request is authenticated")  # the title is kept

    # Confirm: the files changed again but the topic still holds.
    (shop / "shop" / "security.py").write_text(
        SECURITY.replace("SHOP_JWT_SECRET", "SHOP_SIGNING_KEY") + "\n# a comment\n", encoding="utf-8"
    )
    third = ToolContext(workspace=create_workspace(shop, tmp_path / "ws3", ""))
    assert (
        "changed since this topic" in (await _search(third, "read", "how-a-request-is-authenticated")).content
    )
    assert (await _write(third, slug="how-a-request-is-authenticated", confirm=True)).ok
    assert (
        "changed since this topic"
        not in (await _search(third, "read", "how-a-request-is-authenticated")).content
    )


async def test_what_cannot_be_a_topic_is_refused_and_secrets_are_masked(
    isolated_forge_home: Path,
    shop: Path,
    tmp_path: Path,
) -> None:
    context = ToolContext(workspace=create_workspace(shop, tmp_path / "ws", ""))
    assert "`sources`" in (await _write(context, title="T", summary="s", body="x" * 100)).content
    assert "summary" in (await _write(context, title="T", body="x" * 100, sources=["shop/main.py"])).content
    long = await _write(
        context, title="T", summary="s", body="x" * (MAX_BODY_CHARS + 1), sources=["shop/main.py"]
    )
    assert not long.ok and "Split it" in long.content
    lost = await _write(context, title="T", summary="s", body="x" * 100, sources=["nowhere/else.py"])
    assert not lost.ok and "None of the source files exist" in lost.content
    assert all_topics(knowledge_store(context.workspace)) == []

    secret = "sk-proj-" + "a1B2c3D4" * 5  # check_secrets: fake
    kept = await _write(
        context,
        title="Settings",
        summary="Where settings are read",
        body=f"{BODY} The key is {secret}.",
        sources=["shop/security.py"],
    )
    assert kept.ok
    text = (knowledge_store(context.workspace) / "topics" / "settings.md").read_text(encoding="utf-8")
    assert secret not in text and "SHOP_JWT_SECRET" in text  # a value is masked, the name of a setting stays

    assert (await _write(context, slug="settings", delete=True)).ok
    assert all_topics(knowledge_store(context.workspace)) == []
    assert not (await _search(context, "read", "settings")).ok


async def test_the_agenda_names_open_areas_and_unanswered_questions(
    isolated_forge_home: Path, shop: Path, tmp_path: Path
) -> None:
    context = ToolContext(workspace=create_workspace(shop, tmp_path / "ws", ""))
    empty = (await _search(context, "agenda")).content
    assert "Areas with nothing written down yet" in empty and "- shop/ (" in empty
    assert "Questions no topic answers yet" in empty and "agents: which exist" in empty
    await _auth_topic(context)
    after = (await _search(context, "agenda")).content
    assert "- shop/ (" not in after  # the folder has a topic now
    assert "how a request is authenticated" not in after and "the data model" in after
    status = learning_status(context.workspace)
    assert "1 topic(s) written down" in status and "how-a-request-is-authenticated" in status


def test_reading_many_files_brings_one_reminder_to_look_and_one_to_write(
    isolated_forge_home: Path,
    shop: Path,
    tmp_path: Path,
) -> None:
    context = ToolContext(workspace=create_workspace(shop, tmp_path / "ws", ""))
    for number in range(READS_BEFORE_REMINDER):
        context.reads.record(f"shop/file_{number}.py", b"x")
    assert reading_note(context) == ""  # nothing is written down yet, so there is nothing to look at

    import asyncio

    asyncio.run(_auth_topic(ToolContext(workspace=context.workspace)))
    note = reading_note(context)
    assert "check knowledge_search" in note and reading_note(context) == ""  # once

    for number in range(READS_BEFORE_WRITE_REMINDER):
        context.reads.record(f"shop/more_{number}.py", b"x")
    assert "record what you worked out" in reading_note(context) and reading_note(context) == ""

    looked = ToolContext(workspace=context.workspace)
    looked.knowledge_looked = looked.knowledge_written = True
    for number in range(READS_BEFORE_WRITE_REMINDER):
        looked.reads.record(f"shop/again_{number}.py", b"x")
    assert reading_note(looked) == ""  # a session that used the knowledge base is not reminded


def test_learn_has_a_skill_and_the_tools_are_left_out_where_there_is_no_repository() -> None:
    assert "learn-repository" in discover()
    request = learn_request("the orchestration layer")
    assert "learn-repository" in request and "Focus on: the orchestration layer." in request
    names = {tool.name for tool in default_tools()}
    assert {"code_map", "knowledge_search", "knowledge_write"} <= names
    assert not {"code_map", "knowledge_search", "knowledge_write"} & {
        tool.name for tool in session_tools(mode_b=True)
    }
    assert {"code_map", "knowledge_search", "knowledge_write"} <= {
        tool.name for tool in session_tools(mode_b=False)
    }
