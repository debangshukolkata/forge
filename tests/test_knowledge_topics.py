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


def test_topic_files_are_parsed_once_per_version(tmp_path, monkeypatch) -> None:
    from forge.knowledge import topics as topics_module
    from forge.knowledge.topics import Topic, all_topics, save_topic

    for name in ("one", "two"):
        save_topic(
            tmp_path, Topic(slug=name, title=name, summary="s", body="body " * 20, sources={"a.py": "x"})
        )
    all_topics(tmp_path)
    reads: list[str] = []
    real = topics_module._read
    monkeypatch.setattr(topics_module, "_read", lambda path: (reads.append(path.stem), real(path))[1])
    first = all_topics(tmp_path)
    assert reads == []
    first[0].sources["b.py"] = "y"  # a caller's edit must not leak into the cache
    assert "b.py" not in all_topics(tmp_path)[0].sources
    save_topic(tmp_path, Topic(slug="two", title="two", summary="changed", body="body " * 30))
    assert [t.summary for t in all_topics(tmp_path)] == ["s", "changed"]
    assert reads == ["two"]


async def test_a_search_with_one_clear_winner_returns_it_whole_and_read_takes_several_slugs(
    isolated_forge_home: Path, shop: Path, tmp_path: Path
) -> None:
    """KP5 (D-574): the common question costs one call to the model, not a search and then a read."""
    context = ToolContext(workspace=create_workspace(shop, tmp_path / "ws1", ""))
    await _auth_topic(context)
    second = await _write(
        context,
        title="Shop checkout totals",
        summary="How the cart total is computed",
        body="The total of a cart is summed in `cart_total` (shop/main.py:12), after the discounts are taken off.",
        sources=["shop/main.py"],
    )
    assert second.ok, second.content

    found = await _search(context, "search", "authenticated token secret")
    assert "The best match, how-a-request-is-authenticated, in full" in found.content
    assert "SHOP_JWT_SECRET" in found.content  # the body came with the answer
    assert "Shop checkout totals" not in found.content  # only matching topics are listed

    both = await _search(context, "read", "how-a-request-is-authenticated, shop-checkout-totals")
    assert both.ok and "SHOP_JWT_SECRET" in both.content and "cart_total" in both.content
    partly = await _search(context, "read", "shop-checkout-totals nonexistent")
    assert partly.ok and "cart_total" in partly.content and "No topic 'nonexistent'" in partly.content
    assert not (await _search(context, "read", "nonexistent")).ok


def test_titles_and_summaries_about_the_task_or_about_debcraft_are_refused_by_rule() -> None:
    """KU6 (D-574): the checks that need no model."""
    from forge.knowledge.topic_check import rule_problem, verdict_of

    assert rule_problem("How a request is authenticated", "Which function checks the token") == ""
    assert "characters" in rule_problem("Minimal local runner for third party integration endpoint " * 2, "x")
    assert "what you did" in rule_problem("Auth", "I fixed the token check in the router")
    assert "DebCraft" in rule_problem("Setting DEVELOPMENT_INSTANCE_TOKEN for http_request", "how to call it")
    assert verdict_of('Sure: {"verdict": "task", "reason": "a workaround"}') == ("task", "a workaround")
    assert verdict_of('{"verdict": "maybe"}') is None and verdict_of("no json") is None


async def test_a_note_the_reviewer_judges_to_be_about_the_task_goes_to_memory_not_to_the_topics(
    isolated_forge_home: Path, shop: Path, tmp_path: Path, monkeypatch
) -> None:
    from types import SimpleNamespace

    context = ToolContext(workspace=create_workspace(shop, tmp_path / "ws1", ""))
    context.router = object()  # a model is configured; the answer below stands in for it

    answers = iter(
        [
            '{"verdict": "task", "reason": "it is a workaround for one task"}',
            "not json at all",  # an unreadable review never blocks a note
            '{"verdict": "repository", "reason": ""}',
        ]
    )

    async def fake_ask(role: str, request: object, what: str, beat_s: float = 4.0) -> SimpleNamespace:
        assert role == "reviewer"
        return SimpleNamespace(text=next(answers))

    monkeypatch.setattr(context, "ask_model", fake_ask)
    first = await _auth_topic(context)
    assert first.ok and "Not saved as a topic" in first.content and not context.knowledge_written
    assert not (knowledge_store(context.workspace) / "topics").exists() or not list(
        (knowledge_store(context.workspace) / "topics").glob("*.md")
    )
    from forge.config import forge_home
    from forge.memory.scope import scope_of
    from forge.memory.store import MemoryStore

    assert any(
        m.name == "how-a-request-is-authenticated"
        for m in MemoryStore(forge_home(), scope_of(context.workspace)).all()
    )

    second = await _auth_topic(context)
    assert second.ok and "written" in second.content and context.knowledge_written


async def test_the_agenda_lists_topics_that_look_like_task_findings(
    isolated_forge_home: Path, shop: Path, tmp_path: Path
) -> None:
    context = ToolContext(workspace=create_workspace(shop, tmp_path / "ws1", ""))
    await _auth_topic(context)
    store = knowledge_store(context.workspace)
    from forge.knowledge.topics import Topic, save_topic

    save_topic(
        store,
        Topic(
            slug="minimal-runner",
            title="I fixed it with a minimal local runner for the third party endpoint",
            summary="what I did",
            body="x" * 100,
            sources={"shop/main.py": "abc"},
            updated="2026-11-12",
            history=[],
        ),
    )
    agenda = await _search(context, "agenda")
    assert "look like findings of a task" in agenda.content and "minimal-runner" in agenda.content
    assert (
        "how-a-request-is-authenticated" not in agenda.content.split("look like findings")[1].split("\n\n")[0]
    )


def test_use_is_counted_per_topic_and_orders_the_pin_and_the_search(tmp_path: Path) -> None:
    """KU1 to KU3 (D-574): the topics read most come first; without any use the order is as before."""
    from forge.knowledge.topics import Topic, index_lines, ranked
    from forge.knowledge.usage import load_usage, never_read, record

    topics = [
        Topic(slug=f"topic-{n:02d}", title=f"Subject {n}", summary="token handling", sources={"a.py": "1"})
        for n in range(30)
    ]
    assert len(index_lines(topics, {"a.py": "1"}, usage=load_usage(tmp_path))) == 30  # no use: today's order

    record(tmp_path, "project-one", read=["topic-25"], found=["topic-25", "topic-03"])
    record(tmp_path, "project-two", read=["topic-25", "topic-07"])
    usage = load_usage(tmp_path)
    assert usage["topic-25"]["reads"] == 2 and usage["topic-25"]["projects"] == ["project-one", "project-two"]
    assert usage["topic-03"] == {"found": 1} and usage["topic-07"]["reads"] == 1

    lines = index_lines(topics, {"a.py": "1"}, usage=usage)
    assert lines[0].startswith("- topic-25") and lines[1].startswith("- topic-07")
    assert len(lines) == 21 and "and 10 more" in lines[-1]  # 20 listed by use, the rest counted

    # Equal on words: the one read often comes first, and one whose files changed comes after a current one.
    tie = ranked(topics, "token handling", usage=usage, current={"a.py": "1"})
    assert tie[0][1].slug == "topic-25"
    stale = ranked(topics[:2], "token handling", usage={}, current={"a.py": "changed"})
    fresh = ranked(topics[:2], "token handling", usage={}, current={"a.py": "1"})
    assert stale[0][0] < fresh[0][0]
    assert "topic-25" not in never_read(["topic-25", "topic-03"], usage) and "topic-03" in never_read(
        ["topic-25", "topic-03"], usage
    )


async def test_reading_through_the_tool_records_the_use(
    isolated_forge_home: Path, shop: Path, tmp_path: Path
) -> None:
    from forge.knowledge.usage import load_usage

    context = ToolContext(workspace=create_workspace(shop, tmp_path / "ws1", ""))
    await _auth_topic(context)
    await _search(context, "read", "how-a-request-is-authenticated")
    await _search(
        context, "search", "authenticated token secret"
    )  # a clear winner is shown whole: a read too
    usage = load_usage(knowledge_store(context.workspace))
    assert usage["how-a-request-is-authenticated"]["reads"] == 2
    assert usage["how-a-request-is-authenticated"]["found"] == 1
