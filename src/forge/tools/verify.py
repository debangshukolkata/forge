"""Verification tools (spec §9.8): run_tests, verify (the ladder), openapi_check, langgraph_check.

They run fixed commands Forge builds itself (pytest, py_compile, the repo's ruff/flake8/mypy, Forge's check
scripts) in the app's venv, so they don't go through the shell approval flow; like every command, they run
in the sandbox. Output comes back parsed and short."""

from __future__ import annotations

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.verify.checks import langgraph_check, openapi_check
from forge.verify.ladder import VerifyLadder


class RunTests(Tool):
    name = "run_tests"
    description = (
        "Run pytest in the app folder and get a parsed summary (counts, first failures with file:line). "
        "selector: test files or node ids, e.g. 'tests/test_policies_api.py::test_list'; empty = whole suite."
    )

    class Args(ToolArgs):
        selector: str = Field(default="", description="Space-separated test paths/node ids; empty for all.")

    def summary(self, args: RunTests.Args) -> str:
        return f"run tests {args.selector or '(all)'}"

    async def run(self, args: RunTests.Args, context: ToolContext) -> ToolResult:
        step, _ = await VerifyLadder(context).run_tests(args.selector)
        return ToolResult(ok=step.ok, content=step.summary)


class Verify(Tool):
    name = "verify"
    description = (
        "The verify ladder on your changes: compile the changed files, lint and type-check them with the "
        "repo's own tools (when it uses them), then run the tests for the touched modules (full=true: the "
        "whole suite). Stops at the first failing step. Use it after each change."
    )

    class Args(ToolArgs):
        full: bool = False

    def summary(self, args: Verify.Args) -> str:
        return "verify (full suite)" if args.full else "verify changes"

    async def run(self, args: Verify.Args, context: ToolContext) -> ToolResult:
        report = await VerifyLadder(context).run(full=args.full)
        return ToolResult(ok=report.ok, content=report.render())


class OpenApiCheck(Tool):
    name = "openapi_check"
    description = (
        "Build the Flask app and read its OpenAPI spec (flask-smorest): lists paths, methods and schemas "
        "(Mode B: _harness/run_app.py create_app() by default), "
        "and checks that expect_paths are there. By default it calls create_app() of the app package; if "
        "that needs configuration, pass setup: Python code that defines `app`, e.g. using the repo's test "
        "config ('from tests.conftest import make_test_config\\nfrom claims_app import create_app\\n"
        'app = create_app(make_test_config("sqlite://"))\').'
    )

    class Args(ToolArgs):
        expect_paths: list[str] = Field(default_factory=list, description="e.g. ['/api/policies/']")
        setup: str | None = None

    def summary(self, args: OpenApiCheck.Args) -> str:
        return f"openapi check {' '.join(args.expect_paths)}".strip()

    async def run(self, args: OpenApiCheck.Args, context: ToolContext) -> ToolResult:
        outcome = await openapi_check(context, args.setup, args.expect_paths)
        return ToolResult(ok=outcome.ok, content=outcome.text)


class LangGraphCheck(Tool):
    name = "langgraph_check"
    description = (
        "Import a LangGraph graph (or a no-argument function that builds one), compile it and list its "
        "nodes and edges; checks that expect_nodes exist. target: 'package.module:name'. If the builder "
        "needs arguments, pass setup instead: Python code that assigns `graph`, with a fake LLM, e.g. "
        "'from langchain_core.language_models.fake_chat_models import FakeListChatModel\\n"
        "from app.graphs.triage import build_graph\\n"
        'graph = build_graph(FakeListChatModel(responses=["x"]))\'.'
    )

    class Args(ToolArgs):
        target: str | None = None
        setup: str | None = None
        expect_nodes: list[str] = Field(default_factory=list)

    def summary(self, args: LangGraphCheck.Args) -> str:
        return f"langgraph check {args.target or '(setup)'}"

    async def run(self, args: LangGraphCheck.Args, context: ToolContext) -> ToolResult:
        outcome = await langgraph_check(context, args.target, args.setup, args.expect_nodes)
        return ToolResult(ok=outcome.ok, content=outcome.text)
