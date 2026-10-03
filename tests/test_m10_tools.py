"""M10: web tools (offline parts), browser + http_request against the running fixture app (Swagger UI in
headless Edge — the M10 acceptance), user memory and custom commands."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge.memory.store import CommandStore, MemoryStore
from forge.toolkit.base import ToolContext
from forge.tools.browser import BrowserClose, BrowserConsole, BrowserOpen, HttpRequest, local_url
from forge.tools.web import (
    WebCache,
    WebFetch,
    WebSearch,
    html_to_text,
    parse_duckduckgo,
    search_chain,
    search_provider,
)
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO

FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"

EXPORT_ROUTE = '''from __future__ import annotations

from flask.views import MethodView
from flask_smorest import Blueprint

blp = Blueprint("exports", __name__, url_prefix="/api/exports", description="Claim exports")


@blp.route("/")
class ExportList(MethodView):
    def get(self) -> dict[str, int]:
        """List claim exports."""
        return {"count": 0}
'''


# --- web (no network) ---


def test_html_to_text_keeps_the_readable_parts() -> None:
    page = """<html><head><title>Flask-Smorest &amp; you</title><script>alert(1)</script></head>
    <body><nav>menu</nav><h1>Pagination</h1><p>Use   <code>paginate</code> on a view.</p>
    <pre>@blp.paginate()
def get(self): ...</pre><ul><li>one</li><li>two</li></ul><footer>legal</footer></body></html>"""
    title, text = html_to_text(page)
    assert title == "Flask-Smorest & you"
    assert "# Pagination" in text and "Use paginate on a view." in text.replace("<code>", "")
    assert "@blp.paginate()\ndef get(self): ..." in text and "- one" in text
    assert "alert" not in text and "menu" not in text and "legal" not in text


def test_web_cache_expires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = WebCache(tmp_path)
    cache.put("k", {"a": 1})
    assert cache.get("k") == {"a": 1}
    monkeypatch.setattr("forge.tools.web.time.time", lambda: 10**12)
    assert cache.get("k") is None


async def test_web_search_providers_without_a_key(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    tavily = ToolContext(workspace=workspace, web_search_provider="tavily")
    result = await WebSearch().run(WebSearch.Args(query="flask-smorest pagination"), tavily)
    assert not result.ok and "TAVILY_API_KEY" in result.content
    off = await WebSearch().run(
        WebSearch.Args(query="x"), ToolContext(workspace=workspace, web_search_provider="off")
    )
    assert not off.ok and "turned off" in off.content
    assert search_provider(ToolContext(workspace=workspace)) == "duckduckgo"  # auto, no key
    refused = await WebFetch().run(
        WebFetch.Args(url="file:///C:/Windows/win.ini"), ToolContext(workspace=workspace)
    )
    assert not refused.ok


DDG_PAGE = """<div class="result results_links"><div class="links_main">
<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fflask-smorest.readthedocs.io%2Fen%2Flatest%2Fpagination.html&amp;rut=abc">Pagination &mdash; flask-smorest</a>
<a class="result__snippet" href="#">Use the <b>paginate</b> decorator to paginate a view.</a></div></div>
<div class="result result--ad"><a class="result__a" href="https://duckduckgo.com/y.js?ad=1">Ad</a></div>
<div class="result"><a class="result__a" href="https://github.com/marshmallow-code/flask-smorest">flask-smorest on GitHub</a>
<a class="result__snippet">Source code.</a></div>"""


def test_duckduckgo_results_are_parsed_and_links_unwrapped() -> None:
    results = parse_duckduckgo(DDG_PAGE, 5)
    assert results == [
        {
            "title": "Pagination — flask-smorest",
            "url": "https://flask-smorest.readthedocs.io/en/latest/pagination.html",
            "content": "Use the paginate decorator to paginate a view.",
        },
        {
            "title": "flask-smorest on GitHub",
            "url": "https://github.com/marshmallow-code/flask-smorest",
            "content": "Source code.",
        },
    ]


@pytest.mark.live
async def test_duckduckgo_search_finds_documentation(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    """Real network call (no key): DuckDuckGo's HTML results. Skips when blocked by a proxy or rate limit."""
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    result = await WebSearch().run(
        WebSearch.Args(query="flask-smorest pagination", max_results=3), ToolContext(workspace=workspace)
    )
    if not result.ok:
        pytest.skip(result.content)
    assert "(search: duckduckgo)" in result.content and "flask-smorest" in result.content.lower()


def test_browser_and_http_tools_only_reach_the_local_machine() -> None:
    assert local_url("http://127.0.0.1:5000/swagger-ui") is None
    assert local_url("http://localhost:8000/api") is None
    assert local_url("https://example.com") is not None
    assert local_url("http://127.0.0.1.evil.com/") is not None
    assert local_url("file:///C:/x") is not None


# --- memory and custom commands ---


def test_memory_store_redacts_and_indexes(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    memory = store.add("Always ask before adding a new dependency.\nThe user said so on day one.")
    assert store.get(memory.name) is not None and memory.kind == "user"
    index = store.index()
    assert index is not None and "Always ask before adding a new dependency." in index
    assert (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8").count("\n") == 1
    assert store.delete(memory.name) and store.all() == []
    assert not store.delete("../../config")


def test_project_memories_stay_in_their_scope_and_are_redacted(tmp_path: Path) -> None:
    mine, other = MemoryStore(tmp_path, "repo:a-1"), MemoryStore(tmp_path, "repo:b-2")
    saved = mine.save(
        "db-quirk", "orders are soft-deleted", "project", "api_key=abc123def456ghi789jkl"
    )  # check_secrets: fake
    assert "abc123def456ghi789jkl" not in saved.text
    assert other.get("db-quirk") is None and MemoryStore(tmp_path).get("db-quirk") is None
    assert mine.save("db-quirk", "updated", "project", "replaced").text == "replaced"
    assert len(mine.all()) == 1


def test_custom_commands_expand_arguments(tmp_path: Path) -> None:
    folder = tmp_path / "commands"
    folder.mkdir()
    (folder / "endpoint.md").write_text(
        "Add a GET endpoint for $ARGUMENTS following the claims pattern.", "utf-8"
    )
    store = CommandStore(tmp_path)
    assert store.names() == ["endpoint"]
    assert store.expand("endpoint", " policies by holder ") == (
        "Add a GET endpoint for policies by holder following the claims pattern."
    )
    assert store.expand("..\\evil", "") is None and store.expand("missing", "") is None


# --- the running fixture app: http_request and Swagger UI in headless Edge ---


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


@pytest.fixture
def app_with_new_endpoint(tmp_path: Path) -> Iterator[tuple[Workspace, int]]:
    """The fixture app, in a workspace where 'Forge' added GET /api/exports/, running on a free port."""
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    workspace = create_workspace(FIXTURE_REPO, tmp_path / "ws", "backend")
    workspace.write_text("backend/claims_app/api/exports/__init__.py", "")
    workspace.write_text("backend/claims_app/api/exports/routes.py", EXPORT_ROUTE)
    init, _ = workspace.read_text("backend/claims_app/api/__init__.py")
    init = init.replace(
        "from claims_app.api.policies.routes import blp as policies_blp\n",
        "from claims_app.api.policies.routes import blp as policies_blp\n"
        "from claims_app.api.exports.routes import blp as exports_blp\n",
    ).replace(
        "    api.register_blueprint(policies_blp)\n",
        "    api.register_blueprint(policies_blp)\n    api.register_blueprint(exports_blp)\n",
    )
    workspace.write_text("backend/claims_app/api/__init__.py", init)
    port = _free_port()
    env = workspace.info.python_env
    assert env is not None
    variables = env.command_env() | {"DATABASE_URL": f"sqlite:///{tmp_path / 'app.db'}", "JWT_SECRET": "x"}
    process = subprocess.Popen(
        [env.python, "-m", "flask", "--app", "claims_app:create_app()", "run", "--port", str(port)],
        cwd=workspace.app_dir,
        env=variables,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.3)
    yield workspace, port
    process.kill()
    process.wait(timeout=10)


async def test_http_request_smoke_tests_the_local_api(app_with_new_endpoint: tuple[Workspace, int]) -> None:
    workspace, port = app_with_new_endpoint
    context = ToolContext(workspace=workspace)
    result = await HttpRequest().run(HttpRequest.Args(url=f"http://127.0.0.1:{port}/api/exports/"), context)
    assert result.ok and "HTTP 200" in result.content and '"count": 0' in result.content
    refused = await HttpRequest().run(HttpRequest.Args(url="https://example.com/"), context)
    assert not refused.ok and "localhost" in refused.content


@pytest.mark.e2e
async def test_swagger_ui_shows_the_new_endpoint_in_headless_edge(
    app_with_new_endpoint: tuple[Workspace, int],
) -> None:
    """M10 acceptance: Swagger UI of the fixture opens in headless Edge and the new endpoint is visible."""
    pytest.importorskip("playwright.async_api")
    workspace, port = app_with_new_endpoint
    context = ToolContext(workspace=workspace)
    try:
        opened = await BrowserOpen().run(
            BrowserOpen.Args(url=f"http://127.0.0.1:{port}/swagger-ui", wait_for="/api/exports/"), context
        )
        if not opened.ok and ("ERR_INTERNET" in opened.content or "net::" in opened.content):
            pytest.skip("Swagger UI assets come from a CDN and the network is unavailable")
        assert opened.ok, opened.content
        assert "/api/exports/" in opened.content and "/api/claims/" in opened.content
        assert context.browser is not None and context.browser.channel == "msedge"
        console = await BrowserConsole().run(BrowserConsole.Args(), context)
        assert "pageerror" not in console.content
    finally:
        await BrowserClose().run(BrowserClose.Args(), context)


def test_fixture_venv_env_is_isolated() -> None:
    assert "PYTHONPATH" not in os.environ or "forge" not in os.environ.get("PYTHONPATH", "")


def test_serpapi_results_and_provider_order(original_repo: Path, tmp_path: Path) -> None:
    from forge.config import Secrets
    from forge.tools.web import parse_serpapi

    data = {
        "organic_results": [
            {
                "title": "Pagination",
                "link": "https://flask-smorest.readthedocs.io/p.html",
                "snippet": "Use paginate.",
            },
            {"title": "no link"},
        ]
    }
    assert parse_serpapi(data, 5) == [
        {
            "title": "Pagination",
            "url": "https://flask-smorest.readthedocs.io/p.html",
            "content": "Use paginate.",
        }
    ]
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    serp = Secrets({"SERPAPI_API_KEY": "serp-test-key"}, None)  # check_secrets: fake
    both = Secrets(
        {"SERPAPI_API_KEY": "serp-test-key", "TAVILY_API_KEY": "tvly-test"}, None
    )  # check_secrets: fake
    assert search_chain(ToolContext(workspace=workspace, secrets=serp))[0] == ["duckduckgo", "serpapi"]
    assert search_chain(ToolContext(workspace=workspace, secrets=both))[0] == [
        "duckduckgo",
        "serpapi",
        "tavily",
    ]
    assert (
        search_provider(ToolContext(workspace=workspace, secrets=both, web_search_provider="serpapi"))
        == "serpapi"
    )


async def test_auto_falls_back_duckduckgo_then_serpapi_then_azure(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.config import Secrets

    async def blocked(query: str, max_results: int) -> list[dict[str, str]]:
        raise ValueError("DuckDuckGo refused the request (rate limit / bot check)")

    async def quota(key: str, query: str, max_results: int) -> list[dict[str, str]]:
        raise ValueError("SerpAPI returned HTTP 429 Your account has run out of searches.")

    async def azure(query: str) -> tuple[str, list[dict[str, str]]]:
        return "An answer.", [{"url": "https://docs.example/a", "title": "A"}]

    monkeypatch.setattr("forge.tools.web.duckduckgo_search", blocked)
    monkeypatch.setattr("forge.tools.web.serpapi_search", quota)
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    secrets = Secrets({"SERPAPI_API_KEY": "serp-test-key"}, None)  # check_secrets: fake
    context = ToolContext(workspace=workspace, secrets=secrets, hosted_search=azure)
    result = await WebSearch().run(WebSearch.Args(query="fallback check"), context)
    assert result.ok and "(search: azure)" in result.content
    assert "duckduckgo: ValueError" in result.content and "serpapi: ValueError" in result.content

    context = ToolContext(workspace=workspace, secrets=secrets)  # no azure: every provider fails
    failed = await WebSearch().run(WebSearch.Args(query="fallback check 2"), context)
    assert not failed.ok and "every provider" in failed.content


async def test_serpapi_without_a_key_says_how_to_enable_it(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, web_search_provider="serpapi")
    result = await WebSearch().run(WebSearch.Args(query="x"), context)
    assert not result.ok and "SERPAPI_API_KEY" in result.content


@pytest.mark.live
async def test_serpapi_search_finds_documentation(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.config import load_secrets
    from tests.conftest import REPO_ROOT

    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("SERPAPI_API_KEY"):
        pytest.skip("SERPAPI_API_KEY not in .env")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, secrets=secrets, web_search_provider="serpapi")
    result = await WebSearch().run(
        WebSearch.Args(query="python requests library documentation", max_results=3), context
    )
    assert result.ok, result.content
    assert "(search: serpapi)" in result.content and result.content.count("https://") >= 2
    assert "requests" in result.content.lower()
    assert secrets.get("SERPAPI_API_KEY") not in result.content


def test_responses_url_citations_are_collected() -> None:
    from forge.llm.translate_responses import from_responses_output

    payload = {
        "output": [
            {"type": "web_search_call", "id": "ws_1", "status": "completed"},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "flask-smorest 0.47.0 ([pypi.org](https://pypi.org/project/flask-smorest/))",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url": "https://pypi.org/project/flask-smorest/",
                                "title": "flask-smorest · PyPI",
                            }
                        ],
                    }
                ],
            },
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "status": "completed",
    }
    response = from_responses_output(payload)
    assert response.text.startswith("flask-smorest 0.47.0")
    assert response.citations == [
        {"url": "https://pypi.org/project/flask-smorest/", "title": "flask-smorest · PyPI"}
    ]


async def test_azure_search_provider_formats_answer_and_sources(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    calls: list[str] = []

    async def hosted(query: str) -> tuple[str, list[dict[str, str]]]:
        calls.append(query)
        return "0.47.0 is the latest.", [
            {"url": "https://pypi.org/project/flask-smorest/", "title": "PyPI"}
        ] * 2

    context = ToolContext(workspace=workspace, web_search_provider="azure", hosted_search=hosted)
    first = await WebSearch().run(WebSearch.Args(query="latest flask-smorest"), context)
    again = await WebSearch().run(WebSearch.Args(query="latest flask-smorest"), context)
    assert first.ok and "(search: azure)" in first.content and "0.47.0 is the latest." in first.content
    assert first.content.count("https://pypi.org/project/flask-smorest/") == 1  # sources de-duplicated
    assert again.content == first.content and calls == ["latest flask-smorest"]  # cached for 24 h
    missing = await WebSearch().run(
        WebSearch.Args(query="x"), ToolContext(workspace=workspace, web_search_provider="azure")
    )
    assert not missing.ok


@pytest.mark.live
async def test_azure_built_in_web_search(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Azure OpenAI's own web_search tool through Forge's router (cost recorded like any call)."""
    from forge.config import load_config, load_secrets
    from forge.llm.router import LLMRouter
    from forge.tools.web import azure_hosted_search
    from tests.conftest import REPO_ROOT

    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    router = LLMRouter(load_config(isolated_forge_home), secrets)
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(
        workspace=workspace,
        web_search_provider="azure",
        hosted_search=azure_hosted_search(router, "summariser"),
    )
    result = await WebSearch().run(
        WebSearch.Args(query="What is the latest released version of flask-smorest?"), context
    )
    assert result.ok, result.content
    assert "https://" in result.content.split("Sources:")[1]
    assert router.cost.total_usd > 0


async def test_the_verifier_may_only_write_below_tests_e2e(tmp_path: Path, original_repo: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.files import WriteFile
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, write_only_under="backend/tests/e2e/")
    refused = await WriteFile().run(
        WriteFile.Args(path="backend/claims_app/app.py", content="x = 1\n"), context
    )
    assert not refused.ok and "only write below" in refused.content
    accepted = await WriteFile().run(
        WriteFile.Args(path="backend/tests/e2e/test_ui.py", content="def test_x():\n    pass\n"), context
    )
    assert accepted.ok


def test_the_verifier_is_a_built_in_subagent_type() -> None:
    from forge.subagents.spawn_tool import SpawnSubagent
    from forge.tools.parity import BUILT_IN_TYPES

    assert "verifier" in BUILT_IN_TYPES and "verifier" in SpawnSubagent.description


async def test_the_verifier_may_delete_only_its_own_files(tmp_path: Path, original_repo: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.files import DeleteFile, WriteFile
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, write_only_under="backend/tests/e2e/")
    await WriteFile().run(
        WriteFile.Args(path="backend/tests/e2e/tmp_check.py", content="x = 1" + chr(10)), context
    )
    refused = await DeleteFile().run(DeleteFile.Args(path="backend/claims_app/errors.py"), context)
    assert not refused.ok and "only delete files below" in refused.content
    assert (await DeleteFile().run(DeleteFile.Args(path="backend/tests/e2e/tmp_check.py"), context)).ok
    assert not workspace.path_of("backend/tests/e2e/tmp_check.py").exists()
