"""Live acceptance of the revamped core (D-155..D-160): the real model uses memory, the shell for checks, a
subagent, recovers from a failing test on its own, and /init writes FORGE.md. Run with: pytest -m live"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import forge_home
from forge.memory.scope import repo_level_dir, scope_of
from forge.memory.store import MemoryStore
from forge.protocol.events import EventType
from tests.test_live_agent import events_of, make_host, run_turn

pytestmark = pytest.mark.live
__all__ = ["make_host"]  # the fixture comes from test_live_agent


def tool_names(host) -> list[str]:  # type: ignore[no-untyped-def]
    return [e.payload["name"] for e in events_of(host, EventType.TOOL_CALL_STARTED)]


async def test_model_saves_a_stated_preference_as_a_memory(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("auto")
    await run_turn(
        host,
        "For this project, remember this for future sessions: we always write tests with pytest fixtures and "
        "never use unittest.TestCase. Save it to memory, then confirm in one line.",
    )
    assert "memory_write" in tool_names(host)
    scope = scope_of(host.workspace)
    saved = [*MemoryStore(forge_home(), scope).all(), *MemoryStore(forge_home()).all()]
    assert any("fixture" in m.text.lower() or "unittest" in m.text.lower() for m in saved), saved


async def test_model_uses_a_saved_memory_in_a_new_session(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("auto")
    MemoryStore(forge_home(), scope_of(host.workspace)).save(
        "staging-api-path",
        "base path of the staging claims API",
        "reference",
        "The staging claims API base path is /v7/claims-core (not /api).",
    )
    host.refresh_memory_pin()
    await run_turn(host, "What is the base path of the staging claims API? Answer in one line.")
    answer = " ".join(e.payload.get("text", "") for e in events_of(host, EventType.MESSAGE_DONE))
    assert "/v7/claims-core" in answer, answer


async def test_model_fixes_a_failing_test_by_running_it_itself(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("auto")
    workspace = host.workspace
    workspace.write_text("backend/claims_app/mathutil.py", "def add(a, b):\n    return a - b\n")
    test_source = "from claims_app.mathutil import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    workspace.write_text("backend/tests/test_mathutil.py", test_source)
    await run_turn(
        host,
        "tests/test_mathutil.py is failing. Find out why and fix the code, not the test. Run the test to "
        "confirm it passes.",
    )
    names = tool_names(host)
    assert any(n in ("run_command", "python_run") for n in names), names  # it ran pytest itself
    assert workspace.path_of("backend/tests/test_mathutil.py").read_text(encoding="utf-8") == test_source
    assert "a + b" in workspace.path_of("backend/claims_app/mathutil.py").read_text(encoding="utf-8")
    # (The fixture's own Python environment may lack pytest on this machine; whether the model then installs
    # it is the model's call. What matters here: it ran the test itself, and fixed the code, not the test.)


async def test_model_delegates_a_search_to_the_explore_subagent(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("auto")
    await run_turn(
        host,
        "Use a subagent (spawn_subagent with the explore type) to find which file defines the app's "
        "error classes, then tell me the file path in one line.",
    )
    assert "spawn_subagent" in tool_names(host)
    assert events_of(host, EventType.AGENT_STARTED), "the subagent should be tracked"
    answer = " ".join(e.payload.get("text", "") for e in events_of(host, EventType.MESSAGE_DONE))
    assert "errors.py" in answer, answer


async def test_init_writes_a_repository_forge_md(make_host) -> None:  # type: ignore[no-untyped-def]
    host = make_host("auto")
    await run_turn(host, "/init")
    path = repo_level_dir(forge_home(), host.workspace, None) / "FORGE.md"
    assert path.exists(), tool_names(host)
    text = path.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 150 and "pytest" in text.lower(), text
    assert isinstance(path, Path)
