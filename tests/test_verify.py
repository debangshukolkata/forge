"""M8: output parsers, the test guard, the verify ladder and the app checks on the real fixture (its venv)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.verify.checks import langgraph_check, openapi_check
from forge.verify.ladder import VerifyLadder
from forge.verify.parsers import (
    error_signature,
    parse_compile,
    parse_lint,
    parse_mypy,
    parse_pytest,
    signature,
)
from forge.verify.test_guard import check_tests
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO

PYTEST_OUTPUT = """\
..F.
================================== FAILURES ===================================
___________________________ test_list_policies ________________________________
tests/test_policies_api.py:41: in test_list_policies
    assert response.status_code == 200
E   assert 500 == 200
=========================== short test summary info ===========================
FAILED tests/test_policies_api.py::test_list_policies - assert 500 == 200
1 failed, 3 passed in 1.24s
"""


def test_pytest_output_is_summarised_with_the_failure_location() -> None:
    report = parse_pytest(PYTEST_OUTPUT)
    assert report.ran and not report.passed
    assert report.counts == {"failed": 1, "passed": 3}
    failure = report.failures[0]
    assert failure.test == "tests/test_policies_api.py::test_list_policies"
    assert failure.error == "assert 500 == 200" and failure.location == "tests/test_policies_api.py:41"
    assert "1 failed, 3 passed" in report.summary()


def test_collection_errors_and_clean_runs() -> None:
    broken = "E   ModuleNotFoundError: No module named 'claims_app.nope'\n1 error in 0.30s\n"
    report = parse_pytest(broken)
    assert not report.passed and "ModuleNotFoundError" in report.failures[0].error
    assert parse_pytest("....\n4 passed in 0.5s\n").passed


def test_lint_mypy_and_compile_diagnostics() -> None:
    assert parse_lint("claims_app/x.py:3:1: F401 `os` imported but unused\n")[0].code == "F401"
    mypy = parse_mypy("claims_app/x.py:7: error: Incompatible return value type  [return-value]\n")
    assert mypy[0].line == 7 and mypy[0].code == "return-value"
    compiled = parse_compile(
        '  File "claims_app/x.py", line 4\n    def (\n        ^\nSyntaxError: invalid syntax\n'
    )
    assert compiled[0].path == "claims_app/x.py" and compiled[0].code == "SyntaxError"


def test_the_same_failure_has_the_same_signature_whatever_the_numbers() -> None:
    first = error_signature(PYTEST_OUTPUT)
    second = error_signature(PYTEST_OUTPUT.replace("41", "57").replace("1.24s", "3.02s"))
    assert first is not None and first == second
    assert signature("KeyError at 0x7f00ab12 in C:\\tmp\\x.py line 12") == signature(
        "KeyError at 0x7f99cc00 in C:\\temp\\y.py line 99"
    )


# --- On a workspace of the fixture ------------------------------------------------------------


FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """The fixture repo with its full venv (flask, pytest, langgraph): these checks run the real app."""
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    return create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")


@pytest.fixture
def context(workspace: Workspace) -> ToolContext:
    return ToolContext(workspace=workspace, shell=ShellSession(workspace, sandbox="off"))


def test_the_guard_flags_weakened_and_skipped_tests(workspace: Workspace) -> None:
    path = workspace.path_of("backend/tests/test_claims_api.py")
    text = path.read_text(encoding="utf-8")
    first_assert = text.index("    assert ")
    line_end = text.index("\n", first_assert)
    weakened = text[:first_assert] + "    assert True" + text[line_end:]
    weakened = weakened.replace("def test_", "@pytest.mark.skip\ndef test_", 1)
    path.write_text(weakened, encoding="utf-8")

    problems = [f.problem for f in check_tests(workspace)]
    assert any("trivially-true" in p for p in problems)
    assert any("skipped" in p for p in problems)
    assert all(f.blocking for f in check_tests(workspace))


def test_new_tests_that_assert_nothing_are_reported(workspace: Workspace) -> None:
    new = workspace.path_of("backend/tests/test_new_thing.py")
    new.write_text("def test_nothing():\n    x = 1\n\ndef test_real():\n    assert 1 + 1 == 2\n", "utf-8")
    findings = check_tests(workspace)
    assert [(f.test, f.blocking) for f in findings] == [("test_nothing", False)]


async def test_ladder_stops_at_a_syntax_error(context: ToolContext, workspace: Workspace) -> None:
    errors = workspace.path_of("backend/claims_app/errors.py")
    errors.write_text(errors.read_text(encoding="utf-8") + "\ndef broken(:\n", encoding="utf-8")
    report = await VerifyLadder(context).run()
    assert not report.ok
    assert [s.name for s in report.steps] == ["compile"]
    assert "claims_app/errors.py" in report.steps[0].summary


async def test_ladder_runs_the_tests_of_the_touched_module(
    context: ToolContext, workspace: Workspace
) -> None:
    service = workspace.path_of("backend/claims_app/services/claims_service.py")
    source = service.read_text(encoding="utf-8")
    service.write_text(source + "\n\ndef helper_added_by_forge() -> int:\n    return 1\n", encoding="utf-8")
    ladder = VerifyLadder(context)
    selector = ladder.targeted_tests(
        ["claims_app/services/claims_service.py"], ["claims_app/services/claims_service.py"]
    )
    assert "test_claims_api.py" in selector and "test_triage_graph.py" not in selector
    report = await ladder.run()
    assert report.ok, report.render()
    assert report.tests is not None and report.tests.counts.get("passed", 0) > 0
    assert context.last_verified_step == context.step  # a passing test run is evidence


async def test_ladder_reports_a_failing_test_with_its_signature(
    context: ToolContext, workspace: Workspace
) -> None:
    test_file = workspace.path_of("backend/tests/test_policies_api.py")
    test_file.write_text(
        test_file.read_text(encoding="utf-8") + "\n\ndef test_injected_failure():\n    assert 1 == 2\n",
        encoding="utf-8",
    )
    report = await VerifyLadder(context).run()
    assert not report.ok
    assert "test_injected_failure" in report.render() and report.signature


async def test_openapi_check_lists_the_fixture_endpoints(context: ToolContext) -> None:
    setup = (
        "from tests.conftest import make_test_config\n"
        "from claims_app import create_app\n"
        'app = create_app(make_test_config("sqlite://"))'
    )
    outcome = await openapi_check(context, setup, ["/api/claims/", "/api/nope/"])
    assert "/api/claims/" in outcome.text
    assert not outcome.ok and "MISSING expected paths: /api/nope/" in outcome.text


async def test_langgraph_check_compiles_the_triage_graph(context: ToolContext) -> None:
    setup = (
        "from langchain_core.language_models.fake_chat_models import FakeListChatModel\n"
        "from claims_app.graphs.triage_graph import build_triage_graph\n"
        'graph = build_triage_graph(FakeListChatModel(responses=["x"]))'
    )
    outcome = await langgraph_check(context, None, setup, ["__start__"])
    assert outcome.ok, outcome.text
    assert "->" in outcome.text
    needs_args = await langgraph_check(context, "claims_app.graphs.triage_graph:build_triage_graph", None, [])
    assert not needs_args.ok and "needs arguments" in needs_args.text


def test_fixture_is_present() -> None:
    assert (FIXTURE_BACKEND / "claims_app").exists()


def test_setup_errors_carry_their_reason(tmp_path: Path) -> None:
    """The Mode B live run found this: 'ERROR tests/x.py::t' alone told the agent nothing."""
    import subprocess
    import sys

    from forge.verify.ladder import PYTEST_ARGS

    (tmp_path / "test_missing_fixture.py").write_text(
        "def test_uses_client(client):\n    assert client\n", "utf-8"
    )
    run = subprocess.run(
        [sys.executable, "-m", "pytest", *PYTEST_ARGS.split(), "test_missing_fixture.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    report = parse_pytest(run.stdout)
    assert not report.passed and report.failures
    assert "fixture 'client' not found" in report.failures[0].error, report.summary()


def test_the_guard_flags_stubs_in_production_code(workspace: Workspace) -> None:
    # Seen live: a CLI shipped fake Azure clients ("not intended for production"; tests "can monkeypatch").
    from forge.verify.test_guard import check_stubs

    workspace.write_text(
        "backend/claims_app/services/llm_client.py",
        'def call_model(prompt):\n    """Calls the model.\n\n    Not intended for production use."""\n'
        '    return "ok"\n',
    )
    workspace.write_text("backend/tests/test_fake.py", '"""Uses a stub implementation."""\n')
    findings = check_stubs(workspace)
    assert [f.path for f in findings] == ["backend/claims_app/services/llm_client.py:4"]
    assert findings[0].blocking and "only tests may use fakes" in findings[0].problem
