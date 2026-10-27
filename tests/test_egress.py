"""D-503: outbound text that repeats the user's code is refused before it leaves the machine."""

from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import quote

import pytest

from forge.safety.egress import EgressGuard

SECRET_CODE = """
def reconcile_ledger(entries, tolerance=0.01):
    totals = {}
    for entry in entries:
        totals[entry.account_id] = totals.get(entry.account_id, 0) + entry.amount_cents
    return {k: v for k, v in totals.items() if abs(v) > tolerance}
"""


@pytest.fixture
def guard(tmp_path: Path) -> EgressGuard:
    (tmp_path / "billing").mkdir()
    (tmp_path / "billing" / "ledger.py").write_text(SECRET_CODE, encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text(
        "const vendored_value = compute(a, b, c, d, e, f, g, h);"
    )
    return EgressGuard(tmp_path)


def test_a_short_plain_query_goes_out(guard: EgressGuard) -> None:
    assert guard.check_text("pandas read_csv usecols dtype parameter") is None
    assert guard.check_text("fastapi background tasks vs celery") is None


def test_a_pasted_function_is_refused(guard: EgressGuard) -> None:
    line = "totals[entry.account_id] = totals.get(entry.account_id, 0) + entry.amount_cents"
    assert "repeats code" in (guard.check_text(line) or "")


def test_spacing_and_line_breaks_do_not_hide_a_copy(guard: EgressGuard) -> None:
    squeezed = "totals[ entry.account_id ]   =   totals.get( entry.account_id,0 ) + entry.amount_cents"
    assert guard.check_text(squeezed) is not None


def test_an_escaped_address_is_refused(guard: EgressGuard) -> None:
    code = "totals[entry.account_id] = totals.get(entry.account_id, 0) + entry.amount_cents"
    problem = guard.check_text("https://example.org/search?q=" + quote(code), is_address=True)
    assert problem is not None


def test_base64_does_not_hide_a_copy(guard: EgressGuard) -> None:
    blob = base64.b64encode(SECRET_CODE.encode()).decode()
    assert guard.check_text("https://example.org/p/" + blob, is_address=True) is not None


def test_a_long_encoded_looking_string_in_an_address_is_refused_even_when_unknown(guard: EgressGuard) -> None:
    blob = base64.b64encode(b"x" * 90 + bytes(range(60))).decode()
    assert "encoded" in (guard.check_text("https://example.org/?d=" + blob, is_address=True) or "")


def test_a_long_readable_slug_is_fine(guard: EgressGuard) -> None:
    slug = "https://blog.example.com/how-to-fix-the-error-when-trying-to-run-a-python-script-inside-a-docker-container"
    assert guard.check_text(slug, is_address=True) is None


def test_multi_line_or_long_queries_are_refused(guard: EgressGuard) -> None:
    assert guard.check_text("a\nb\nc\nd") is not None
    assert guard.check_text("word " * 200) is not None


def test_vendored_folders_are_not_the_users_code(guard: EgressGuard) -> None:
    assert guard.check_text("const vendored_value = compute(a, b, c, d, e, f, g, h);") is None


def test_what_a_local_tool_showed_the_model_counts_as_the_users_code(tmp_path: Path) -> None:
    guard = EgressGuard(tmp_path)  # nothing on disk
    output = "def secret_rule(order):\n    return order.total_cents > LIMITS['vip_threshold'] and order.region == 'EU'\n"
    assert guard.check_text("order.total_cents > LIMITS['vip_threshold'] and order.region == 'EU'") is None
    guard.remember(output)
    assert (
        guard.check_text("order.total_cents > LIMITS['vip_threshold'] and order.region == 'EU'") is not None
    )


def test_the_check_covers_every_text_value_of_a_call(guard: EgressGuard) -> None:
    code = "totals[entry.account_id] = totals.get(entry.account_id, 0) + entry.amount_cents"
    assert guard.check_arguments("mcp_x", {"a": 1, "nested": {"items": ["fine", code]}}) is not None
    assert guard.check_arguments("web_search", {"query": "python dataclass slots", "max_results": 5}) is None


def test_an_address_the_user_typed_is_theirs_to_send(guard: EgressGuard) -> None:
    blob = base64.b64encode(bytes(range(200))).decode().replace("=", "")
    url = "https://example.org/share?token=" + blob
    assert guard.check_text(url, is_address=True) is not None
    guard.user_addresses = lambda: {url}
    assert guard.check_text(url, is_address=True) is None


@pytest.mark.parametrize(
    "tool",
    [
        "web_search",
        "web_fetch",
        "find_image",
        "fetch_image",
        "find_font",
        "fetch_font",
        "theme_search",
        "library_api",
        "design_inspire",
    ],
)
def test_the_networked_tools_are_flagged(tool: str) -> None:
    from forge.tools.registry import default_tools

    by_name = {t.name: t for t in default_tools()}
    assert by_name[tool].sends_outside


async def test_the_loop_refuses_a_networked_call_that_repeats_project_code(
    original_repo: Path, tmp_path: Path
) -> None:
    """Through the real session host: the guard is built from the workspace's repo copy and runs before the tool does."""
    import json

    import httpx2

    from forge.engine.session_host import SessionHost
    from forge.llm.base import ToolCall
    from forge.protocol.events import EventBus
    from forge.safety.redact import Redactor
    from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
    from forge.tools.registry import ToolRegistry
    from forge.workspace.create import create_workspace
    from tests.helpers import mocked_router

    calls: list[str] = []

    class Outside(Tool):
        name = "web_search"
        read_only = True
        sends_outside = True
        description = "stands in for a networked tool"

        class Args(ToolArgs):
            query: str

        async def run(self, args: Outside.Args, context: ToolContext) -> ToolResult:
            calls.append(args.query)
            return ToolResult(ok=True, content="public result")

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    leaked_line = next(
        line.strip()
        for path in sorted(workspace.repo_dir.rglob("*.py"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if len(line.split()) >= 12 and "(" in line and "=" in line
    )
    host = SessionHost(
        mocked_router(lambda request: httpx2.Response(500)),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    assert host.agent is not None and host.agent.context.egress is not None
    host.agent.tools = ToolRegistry([Outside()])
    results: dict = {}
    batch = [
        ToolCall(
            id=f"c{i}", name="web_search", raw_arguments=json.dumps({"query": q}), arguments={"query": q}
        )
        for i, q in enumerate(["python dataclass slots", leaked_line])
    ]
    await host.agent._run_calls(batch, results)
    assert calls == ["python dataclass slots"]  # the second call never reached the tool
    assert "Not sent" in str(results["c1"]) and "public result" in str(results["c0"])
