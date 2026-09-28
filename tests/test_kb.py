"""M5: Knowledge Base extractors, build, incremental refresh, search and tools (no LLM: the doc writer
is a deterministic function here; tests/test_live_kb.py uses the real model)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from forge.kb.builder import build, status
from forge.kb.facts import collect_facts
from forge.kb.flask_smorest import resolve_import
from forge.kb.knowledge import KnowledgeBase
from forge.kb.python_index import parse_module
from forge.kb.store import PINNED_MARKER, kb_dir_for
from forge.tools.base import ToolContext
from forge.tools.kb import FindReferences, FindSymbol, KbRead, KbSearch, ListSymbols
from forge.workspace.create import create_workspace
from tests.conftest import FIXTURE_REPO


class RecordingWriter:
    """Stands in for the kb_builder model: records which documents were requested."""

    def __init__(self) -> None:
        self.kinds: list[str] = []

    async def __call__(self, kind: str, prompt: str) -> str:
        self.kinds.append(kind)
        if kind == "conventions":
            return (
                "## Top conventions\n- Use flask-smorest MethodView blueprints.\n"
                "- Raw SQL lives in repositories.\n"
            )
        return f"## Purpose\nDocument for {kind}.\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    copy = tmp_path / "claims-repo"
    shutil.copytree(
        FIXTURE_REPO, copy, ignore=shutil.ignore_patterns("venv", "__pycache__", ".pytest_cache", "*.db")
    )
    return copy


@pytest.fixture
async def built(repo: Path, tmp_path: Path) -> tuple[Path, Path, RecordingWriter]:
    writer = RecordingWriter()
    kb_dir = tmp_path / "kb"
    await build(repo, "backend", kb_dir, writer)
    return repo, kb_dir, writer


# --- extractors (spec M5 acceptance: API_CATALOG, DB_SCHEMA, LLM_GRAPHS correct for the fixture) ---


def test_fixture_facts_are_correct() -> None:
    facts = collect_facts(FIXTURE_REPO, "backend")

    endpoints = {(e.method, e.path, e.view) for e in facts.endpoints}
    assert endpoints == {
        ("GET", "/api/claims/", "ClaimList.get"),
        ("POST", "/api/claims/", "ClaimList.post"),
        ("GET", "/api/claims/<int:claim_id>", "ClaimDetail.get"),
        ("POST", "/api/claims/<int:claim_id>/triage", "ClaimTriage.post"),
        ("GET", "/api/policies/active", "list_active_policies"),
        ("GET", "/api/policies/<int:policy_id>", "get_policy"),
    }
    listing = next(e for e in facts.endpoints if e.view == "ClaimList.get")
    assert listing.arguments == ["ClaimQuerySchema (query)"]
    assert listing.responses == ["200 ClaimPageSchema"]
    assert listing.other_decorators == ["jwt_required"]
    assert {b.name: len(b.registered_in) for b in facts.blueprints} == {"claims": 1, "policies": 1}

    claims = next(m for m in facts.models if m.table == "claims")
    assert ("policy_id", "int", "policies.id") in [(c.name, c.type, c.foreign_key) for c in claims.columns]
    assert {(u.function, u.operation) for u in facts.sql_usage if not u.in_tests} >= {
        ("list_claims", "SELECT"),
        ("insert_claim", "INSERT"),
        ("update_claim_triage", "UPDATE"),
    }
    assert [(b.tables, b.env_names) for b in facts.bootstraps] == [
        (["app_config"], ["DB_HOST", "DB_NAME", "DB_PASSWORD", "DB_PORT", "DB_USER"])
    ]
    assert facts.sql_scripts.next_name_example == "V004__<description>.sql"

    graph = facts.graphs[0]
    assert graph.builder == "build_triage_graph" and graph.compiled
    assert [n for n, _ in graph.nodes] == ["classify", "assess_priority", "fraud_check", "summarise"]
    assert ("START", "classify") in graph.edges and ("summarise", "END") in graph.edges
    assert graph.conditional == [
        (
            "classify",
            "route_after_classify",
            {"fraud_check": "fraud_check", "assess_priority": "assess_priority"},
        )
    ]
    assert "BOOTSTRAP_DB_URL" in facts.env_keys and "JWT_SECRET" in facts.env_keys
    assert facts.stack.packages["flask-smorest"] == "==0.47.0"
    assert not any(path.endswith(".env") for path in facts.file_hashes)  # secret files are never read


def test_relative_imports_resolve() -> None:
    module = parse_module(FIXTURE_REPO, "backend/claims_app/api/__init__.py", "backend")
    assert module is not None
    assert resolve_import(module, ".claims.routes") == "claims_app.api.claims.routes"
    assert resolve_import(module, "..db") == "claims_app.db"


# --- build and refresh ---


async def test_build_writes_every_document(built: tuple[Path, Path, RecordingWriter]) -> None:
    _, kb_dir, writer = built

    names = {p.relative_to(kb_dir).with_suffix("").as_posix() for p in kb_dir.rglob("*.md")}
    assert {
        "STACK",
        "COMMANDS",
        "API_CATALOG",
        "DB_SCHEMA",
        "LLM_GRAPHS",
        "ARCHITECTURE",
        "CONVENTIONS",
        "ESSENTIALS",
    } <= names
    assert "modules/claims_app.api.claims" in names and "modules/tests" in names
    assert "architecture" in writer.kinds and "module:claims_app.services" in writer.kinds
    catalog = (kb_dir / "API_CATALOG.md").read_text(encoding="utf-8")
    assert "| POST | `/api/claims/<int:claim_id>/triage` | ClaimTriage.post (MethodView)" in catalog
    schema = (kb_dir / "DB_SCHEMA.md").read_text(encoding="utf-8")
    assert "`app_config`" in schema and "Credentials bootstrap" in schema
    essentials = (kb_dir / "ESSENTIALS.md").read_text(encoding="utf-8")
    assert "Use flask-smorest MethodView blueprints." in essentials and "V004__" in essentials
    assert (kb_dir / "index.sqlite").exists() and (kb_dir / "manifest.json").exists()


async def test_changing_one_file_rewrites_only_its_package_doc(
    built: tuple[Path, Path, RecordingWriter],
) -> None:
    repo, kb_dir, _ = built
    errors = repo / "backend" / "claims_app" / "errors.py"
    errors.write_text(
        errors.read_text(encoding="utf-8") + "\n\nclass ConflictError(ClaimsAppError):\n"
        "    status_code = 409\n",
        encoding="utf-8",
    )
    assert [*status(repo, "backend", kb_dir).modified] == ["backend/claims_app/errors.py"]  # type: ignore[union-attr]

    writer = RecordingWriter()
    report = await build(repo, "backend", kb_dir, writer)

    assert writer.kinds == ["module:claims_app"]  # not the other 9 packages, not the global narratives
    assert report.changes.modified == ["backend/claims_app/errors.py"]
    assert "ConflictError" in (kb_dir / "modules" / "claims_app.md").read_text(encoding="utf-8")
    assert "- modified backend/claims_app/errors.py" in (kb_dir / "ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    assert status(repo, "backend", kb_dir).all == []  # type: ignore[union-attr]


async def test_removed_package_doc_is_deleted(built: tuple[Path, Path, RecordingWriter]) -> None:
    repo, kb_dir, _ = built
    shutil.rmtree(repo / "backend" / "claims_app" / "graphs")

    await build(repo, "backend", kb_dir, RecordingWriter())

    assert not (kb_dir / "modules" / "claims_app.graphs.md").exists()
    assert "No LangGraph graphs found." in (kb_dir / "LLM_GRAPHS.md").read_text(encoding="utf-8")


async def test_pinned_hand_edits_survive_rebuilds(built: tuple[Path, Path, RecordingWriter]) -> None:
    repo, kb_dir, _ = built
    mine = f"{PINNED_MARKER}\n## Top conventions\n- Our own rule.\n"
    (kb_dir / "CONVENTIONS.md").write_text(mine, encoding="utf-8")

    writer = RecordingWriter()
    report = await build(repo, "backend", kb_dir, writer, full=True)

    assert (kb_dir / "CONVENTIONS.md").read_text(encoding="utf-8") == mine
    assert "CONVENTIONS" in report.docs_kept_pinned and "conventions" not in writer.kinds
    assert "Our own rule." in (kb_dir / "ESSENTIALS.md").read_text(encoding="utf-8")


def test_kb_location_is_per_repo_and_app(tmp_path: Path) -> None:
    first = kb_dir_for(tmp_path, FIXTURE_REPO, "backend")
    assert first == kb_dir_for(tmp_path, FIXTURE_REPO, "backend")
    assert first != kb_dir_for(tmp_path, FIXTURE_REPO, "frontend")
    assert first.parent == tmp_path / "kb" and first.name.startswith("sample-repo-")


# --- reading ---


async def test_search_symbols_and_references(built: tuple[Path, Path, RecordingWriter]) -> None:
    _, kb_dir, _ = built
    kb = KnowledgeBase.open(kb_dir)
    assert kb is not None

    graph_hits = kb.search("triage graph conditional routing", kinds=["doc"])
    symbol_hits = kb.search("ClaimsAppError", kinds=["symbol"])

    assert graph_hits[0].name == "LLM_GRAPHS"
    assert symbol_hits[0].name == "ClaimsAppError"
    found = kb.find_symbol("NotFoundError")
    assert found[0]["path"] == "backend/claims_app/errors.py" and found[0]["bases"] == ["ClaimsAppError"]
    assert "backend/claims_app/services/claims_service.py" in {
        p for p, _ in kb.find_references("session_scope")
    }
    assert [q for _, q, _, _ in kb.list_symbols("backend/claims_app/errors.py")][:2] == [
        "ClaimsAppError",
        "NotFoundError",
    ]
    assert kb.read("../../outside") is None  # no path escapes


async def test_kb_tools(
    built: tuple[Path, Path, RecordingWriter], original_repo: Path, tmp_path: Path
) -> None:
    _, kb_dir, _ = built
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, kb=KnowledgeBase.open(kb_dir))
    without = ToolContext(workspace=workspace)

    search = await KbSearch().run(KbSearch.Args(query="which endpoints handle claims"), context)
    read = await KbRead().run(KbRead.Args(doc="API_CATALOG"), context)
    missing = await KbRead().run(KbRead.Args(doc="NOPE"), context)
    symbol = await FindSymbol().run(FindSymbol.Args(name="create_claim"), context)
    refs = await FindReferences().run(FindReferences.Args(name="get_chat_model"), context)
    listed = await ListSymbols().run(ListSymbols.Args(path="backend/claims_app/db.py"), context)
    no_kb = await KbSearch().run(KbSearch.Args(query="x"), without)

    assert search.ok and "API_CATALOG" in search.content
    assert "/api/claims/<int:claim_id>/triage" in read.content
    assert not missing.ok and "Available:" in missing.content
    assert "def create_claim(policy_id: int, amount: float, description: str)" in symbol.content
    assert "backend/claims_app/api/claims/routes.py" in refs.content
    assert "session_scope" in listed.content
    assert no_kb.ok and "/kb build" in no_kb.content  # advice, not a failure (no stuck signal from it)


async def test_workspace_session_pins_kb_essentials(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path
) -> None:
    import asyncio

    from forge.engine.events import EventBus, EventType
    from forge.engine.session_host import SessionHost
    from forge.safety.redact import Redactor
    from tests.helpers import mocked_router

    def unreachable(request: object) -> object:
        raise AssertionError("no LLM call expected")

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    no_kb_host = SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)  # type: ignore[arg-type]
    await no_kb_host.announce_kb_status()
    assert "No knowledge base for this repository yet" in no_kb_host.bus.events_since(0)[-1].payload["text"]
    assert no_kb_host.context_manager.pinned.get("kb_essentials") is None

    await build(
        original_repo, "backend", kb_dir_for(isolated_forge_home, original_repo, "backend"), RecordingWriter()
    )
    host = SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)  # type: ignore[arg-type]
    await host.announce_kb_status()
    await asyncio.sleep(0)

    essentials = host.context_manager.pinned.get("kb_essentials") or ""
    assert "Use flask-smorest MethodView blueprints." in essentials
    assert host.agent is not None and host.agent.context.kb is not None
    assert "kb_search" in host.agent.tools.names()
    assert not [e for e in host.bus.events_since(0) if e.type == EventType.NOTICE]  # up to date: no notice
