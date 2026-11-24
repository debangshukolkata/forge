"""D-642: the recipes of the langchain-agent skill run on the installed LangGraph of the test bed (other versions: see
the docstring of tests/langchain_recipe_check.py)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from forge.engine.session_host import SessionHost
from forge.llm.tokens import count_text_tokens
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.toolkit.base import ToolContext
from forge.tools.http_request import answer_failure
from forge.tools.parity import LoadSkill
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.helpers import mocked_router
from tests.test_agent_platform_pg import VENV_PYTHON

SKILL = REPO_ROOT / "src" / "forge" / "skills" / "langchain-agent"


def test_the_graph_recipe_runs() -> None:
    if not VENV_PYTHON.is_file():
        pytest.skip("the fixture venv is missing (tests/fixtures/agent_platform_pg/requirements.txt)")
    done = subprocess.run(
        [
            str(VENV_PYTHON),
            str(REPO_ROOT / "tests" / "langchain_recipe_check.py"),
            str(SKILL / "recipes"),
            "graph",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0 and "OK graph" in done.stdout, done.stderr[-1500:]


def test_the_recipes_the_skill_names_exist() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for recipe in (SKILL / "recipes").glob("*.py"):
        assert f"recipes/{recipe.name}" in text
        compile(recipe.read_text(encoding="utf-8"), recipe.name, "exec")


async def test_the_skill_brings_its_recipe_the_version_tool_and_the_api_proof(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    context.step = 7
    result = await LoadSkill().run(LoadSkill.Args(name="langchain-agent"), context)
    assert result.ok and "def build_skill_agent(" in result.content
    assert result.meta["attach_tools"] == ["python_libraries"]
    assert context.running_system_step == 7 and context.proof_by_post
    assert (
        count_text_tokens(result.content) < 6000
    )  # more would be cut in the middle (the cap of a tool result)


def test_an_answer_of_200_with_a_failed_run_inside_counts_as_a_failure() -> None:
    assert answer_failure(500, "") == "HTTP 500"
    assert answer_failure(200, '{"status": "failed", "error": "x"}') == "status failed"
    assert answer_failure(200, '{"error": "x"}')
    for good in ('{"status": "ok", "answer": "1"}', '{"answer": "y", "error": null}', "plain", "[1]"):
        assert answer_failure(200, good) == ""


async def test_the_proof_must_run_the_agent_and_must_not_fail(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda request: None), EventBus(redactor=Redactor()), workspace=workspace
    )  # type: ignore[arg-type,return-value]
    assert host.agent is not None
    context = host.agent.context
    context.running_system_step, context.proof_by_post, context.last_code_edit_step = 3, True, 5
    problem = host.agent._skill_proof_problem
    assert "you called no API after" in problem(2)
    context.api_calls["GET http://127.0.0.1:1/api/agents"] = 6
    assert "only made GET calls" in problem(2)
    context.api_calls["POST http://127.0.0.1:1/run"] = 7
    context.api_failed["POST http://127.0.0.1:1/run"] = "status failed"
    assert "status failed" in problem(2)
    context.api_failed.clear()
    assert problem(2) == ""
    assert problem(8) == ""  # nothing was changed in this turn
