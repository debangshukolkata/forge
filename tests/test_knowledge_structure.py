"""The repository's structure index (KL1, D-563): exact facts from the code, kept between projects."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from forge.knowledge.code_map import BY_NAME, EXACT, CodeMap
from forge.knowledge.python_file import describe
from forge.knowledge.structure import STRUCTURE_FILE, load, refresh
from forge.toolkit.base import ToolContext
from forge.tools.code_map_tool import CodeMapTool, knowledge_store, repository_map_pin
from forge.workspace.create import create_workspace

FASTAPI_APP = '''
import os
from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel
from shop.security import current_user
from shop import orders_service

router = APIRouter(prefix="/orders")
app = FastAPI()


class NewOrder(BaseModel):
    item: str
    quantity: int = 1


@router.post("/", response_model=dict)
async def create_order(order: NewOrder, user: dict = Depends(current_user)) -> dict:
    """Place an order"""
    return orders_service.place(order.item, order.quantity, user)


@router.get("/{order_id}")
def read_order(order_id: int) -> dict:
    return orders_service.find(order_id)


app.include_router(router, prefix="/api/v1")
'''
SECURITY = """
import os


def current_user(token: str = "") -> dict:
    return _decode(token)


def _decode(token: str) -> dict:
    secret = os.environ["SHOP_JWT_SECRET"]
    issuer = os.getenv("SHOP_ISSUER", "shop")
    return {"secret": bool(secret), "issuer": issuer}
"""
SERVICE = """
from shop.repository import OrderRepository


def place(item: str, quantity: int, user: dict) -> dict:
    return OrderRepository().insert(item, quantity)


def find(order_id: int) -> dict:
    repository = OrderRepository()
    return repository.fetch_by_number(order_id)
"""
REPOSITORY = """
class OrderRepository:
    def insert(self, item: str, quantity: int) -> dict:
        self._run("INSERT INTO orders (item, quantity) VALUES (%s, %s)")
        return {}

    def fetch_by_number(self, order_id: int) -> dict:
        return self._run("SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id")

    def _run(self, sql: str) -> dict:
        return {}


def explain() -> str:
    return "Update the node from memory, or delete it."
"""


@pytest.fixture
def shop(tmp_path: Path) -> Path:
    root = tmp_path / "shop_repo"
    package = root / "shop"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text(FASTAPI_APP, encoding="utf-8")
    (package / "security.py").write_text(SECURITY, encoding="utf-8")
    (package / "orders_service.py").write_text(SERVICE, encoding="utf-8")
    (package / "repository.py").write_text(REPOSITORY, encoding="utf-8")
    (root / "schema.sql").write_text("CREATE TABLE IF NOT EXISTS customers (id int);\n", encoding="utf-8")
    (root / "web").mkdir()
    (root / "web" / "orders.service.ts").write_text(
        "@Injectable()\nexport class OrdersService {\n  load() { return this.http.get<Order[]>('/api/v1/orders/1'); }\n}\n",
        encoding="utf-8",
    )
    (root / "node_modules").mkdir()
    (root / "node_modules" / "skipped.py").write_text("x = 1\n", encoding="utf-8")
    return root


def _map(root: Path, store: Path) -> CodeMap:
    structure, _ = refresh(root, store)
    return CodeMap(structure)


def test_a_fastapi_endpoint_has_its_full_path_payload_auth_and_tables(shop: Path, tmp_path: Path) -> None:
    code_map = _map(shop, tmp_path / "store")
    endpoints = {f"{e['method']} {e['full_path']}": e for e in code_map.endpoints()}
    assert set(endpoints) == {"POST /api/v1/orders", "GET /api/v1/orders/{order_id}"}  # mount + router prefix

    create = endpoints["POST /api/v1/orders"]
    payload = code_map.payload(create)
    assert len(payload) == 1 and "NewOrder" in payload[0] and "item: str, quantity: int" in payload[0]
    auth = code_map.auth_of(create)
    assert len(auth) == 1 and "current_user" in auth[0] and "shop/security.py:5" in auth[0]
    assert "SHOP_JWT_SECRET" in auth[0] and "SHOP_ISSUER" in auth[0]  # names only, read two calls down
    tables = code_map.tables_of(create["key"])
    assert list(tables) == ["orders"]
    assert tables["orders"] == ("create_order -> place -> OrderRepository.insert", EXACT)

    read = endpoints["GET /api/v1/orders/{order_id}"]
    assert code_map.payload(read) == ["parameter order_id: int"] and code_map.auth_of(read) == []
    reached = code_map.tables_of(read["key"])
    # `repository.fetch_by_number`: the variable's type is not known, one function has that name -> by name
    assert set(reached) == {"orders", "customers"} and reached["customers"][1] == BY_NAME


def test_calls_are_linked_across_files_and_an_english_sentence_is_not_sql(shop: Path, tmp_path: Path) -> None:
    code_map = _map(shop, tmp_path / "store")
    callers = {
        key.partition(":")[2] for key, _, _ in code_map.callers()["shop.repository:OrderRepository.insert"]
    }
    assert callers == {"place"}
    callees = {key.partition(":")[2] for key, _, _ in code_map.edges()["shop.security:current_user"]}
    assert callees == {"_decode"}
    assert code_map.named("OrderRepository.insert") == ["shop.repository:OrderRepository.insert"]
    assert set(code_map.tables()) == {"orders", "customers"}  # "Update the node from memory" adds nothing
    assert any("created in schema.sql" in place for place in code_map.tables()["customers"])
    assert "node_modules/skipped.py" not in code_map.files
    assert code_map.files["web/orders.service.ts"]["http"] == [
        {"method": "GET", "path": "/api/v1/orders/1", "line": 3}
    ]


def test_flask_method_views_blueprints_and_schemas_are_read(tmp_path: Path) -> None:
    code_map = _map(Path("tests/fixtures/sample_repo"), tmp_path / "store")
    endpoints = {f"{e['method']} {e['full_path']}": e for e in code_map.endpoints()}
    assert "POST /api/claims" in endpoints and "GET /api/claims/<int:claim_id>" in endpoints
    create = endpoints["POST /api/claims"]
    assert "ClaimCreateSchema" in code_map.payload(create)[0] and "policy_id" in code_map.payload(create)[0]
    assert "jwt_required" in code_map.auth_of(create)[0]
    assert {"claims", "policies"} <= set(code_map.tables_of(create["key"]))


def test_a_refresh_parses_only_what_changed_and_keeps_the_projects_own_edits_out(
    shop: Path, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    _, first = refresh(shop, store)
    assert len(first.added) == 7 and first.unchanged == 0
    _, second = refresh(shop, store)
    assert second.touched == [] and second.unchanged == 7

    (shop / "shop" / "security.py").write_text(SECURITY + "\n\ndef extra() -> None: ...\n", encoding="utf-8")
    (shop / "shop" / "new_module.py").write_text("def added() -> int:\n    return 1\n", encoding="utf-8")
    (shop / "schema.sql").unlink()
    structure, third = refresh(shop, store)
    assert third.changed == ["shop/security.py"] and third.added == ["shop/new_module.py"]
    assert third.removed == ["schema.sql"] and third.unchanged == 5
    assert CodeMap(structure).named("extra") == ["shop.security:extra"]

    # A file this project changed keeps its stored record: the index is about the user's repository.
    (shop / "shop" / "repository.py").write_text(
        "def rewritten_by_the_project() -> None: ...\n", encoding="utf-8"
    )
    structure, fourth = refresh(shop, store, frozen={"shop/repository.py"})
    assert fourth.touched == []
    assert CodeMap(structure).named("OrderRepository.insert") and not CodeMap(structure).named(
        "rewritten_by_the_project"
    )


def test_a_file_that_does_not_parse_or_an_unreadable_store_never_breaks_the_index(
    shop: Path, tmp_path: Path
) -> None:
    (shop / "shop" / "broken.py").write_text("def nope(:\n", encoding="utf-8")
    store = tmp_path / "store"
    code_map = _map(shop, store)
    assert code_map.broken == ["shop/broken.py"] and len(code_map.endpoints()) == 2
    (store / STRUCTURE_FILE).write_text("{not json", encoding="utf-8")
    assert load(store)["files"] == {}
    assert len(_map(shop, store).files) == 7  # rebuilt from the code


def test_nothing_but_names_and_signatures_is_stored() -> None:
    record = describe(
        'import os\nKEY = "sk-live-not-a-real-key"  # check_secrets: fake\n\ndef f():\n    return os.environ["API_KEY"]\n',
        "m",
    )
    assert "sk-live" not in str(record) and record["env"] == ["API_KEY"]


async def test_the_tool_answers_from_a_store_shared_by_every_project_on_the_repository(
    isolated_forge_home: Path, shop: Path, tmp_path: Path
) -> None:
    first = create_workspace(shop, tmp_path / "ws1", "")
    second = create_workspace(shop, tmp_path / "ws2", "")
    assert knowledge_store(first) == knowledge_store(second)  # by repository path, not by project
    assert str(knowledge_store(first)).startswith(str(isolated_forge_home))

    tool = CodeMapTool()
    detail = await tool.run(
        CodeMapTool.Args(action="endpoint", query="POST /api/v1/orders"), ToolContext(workspace=first)
    )
    assert detail.ok and "needs: body `order`: NewOrder" in detail.content
    assert "reads environment: SHOP_ISSUER, SHOP_JWT_SECRET" in detail.content
    assert "table orders: create_order -> place -> OrderRepository.insert" in detail.content
    assert "[index updated: 7 new" in detail.content and (knowledge_store(first) / STRUCTURE_FILE).is_file()

    again = await tool.run(
        CodeMapTool.Args(action="callers", query="OrderRepository.insert"), ToolContext(workspace=second)
    )
    assert again.ok and "place (shop/orders_service.py:5) [calls]" in again.content
    assert (
        "[index updated" not in again.content
    )  # the second project found the first one's index and nothing changed

    for action, query, expected in [
        ("find", "current_user", "shop/security.py:5: function current_user(token: str='') -> dict"),
        ("file", "shop/repository.py", "class OrderRepository"),
        ("endpoints", "", "GET /api/v1/orders/{order_id} -> read_order"),
        ("callees", "place", "OrderRepository.insert"),
        ("tables", "", "orders: SQL in OrderRepository.insert"),
        ("table", "customers", "GET /api/v1/orders/{order_id}"),
        ("env", "", "SHOP_JWT_SECRET: read in shop/security.py"),
        ("overview", "", "2 web endpoints, 2 tables"),
    ]:
        result = await tool.run(CodeMapTool.Args(action=action, query=query), ToolContext(workspace=second))  # type: ignore[arg-type]
        assert result.ok and expected in result.content, (action, result.content)
    missing = await tool.run(CodeMapTool.Args(action="find"), ToolContext(workspace=second))
    assert not missing.ok

    pin = repository_map_pin(second) or ""
    assert "Map of this repository" in pin and "- shop/: 5 files" in pin
    assert (
        not list(shop.rglob(STRUCTURE_FILE)) and not (shop / ".forge").exists()
    )  # nothing written into the repository
    shutil.rmtree(tmp_path / "ws1")


def test_an_older_copy_is_answered_correctly_but_never_pushes_the_index_back(
    shop: Path, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    old_copy = tmp_path / "old_copy"
    shutil.copytree(shop, old_copy)
    (shop / "shop" / "security.py").write_text(
        SECURITY + "\n\ndef added_later() -> None: ...\n", encoding="utf-8"
    )

    newer, _ = refresh(shop, store, as_of="2026-11-10T09:00:00+00:00")
    assert CodeMap(newer).named("added_later")

    older, report = refresh(old_copy, store, as_of="2026-11-01T09:00:00+00:00")
    assert report.changed == ["shop/security.py"] and not CodeMap(older).named(
        "added_later"
    )  # right for that copy
    assert CodeMap(load(store)).named("added_later")  # the stored index still describes the newer code
    assert load(store)["as_of"] == "2026-11-10T09:00:00+00:00"

    (shop / "shop" / "security.py").write_text(SECURITY, encoding="utf-8")
    refresh(shop, store, as_of="2026-11-11T09:00:00+00:00")  # a newer copy moves it forward
    assert not CodeMap(load(store)).named("added_later") and load(store)["as_of"].startswith("2026-11-11")


async def test_the_settings_report_names_what_the_code_needs_and_the_env_files_lack(
    isolated_forge_home: Path, tmp_path: Path
) -> None:
    repo = tmp_path / "svc"
    (repo / "svc").mkdir(parents=True)
    (repo / "svc" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "svc" / "settings.py").write_text(
        "import os\n\n"
        'HOST = os.getenv("QUEUE_HOST")\n'  # module level, no default
        'REGION = os.getenv("QUEUE_REGION", "eu")\n\n\n'
        "class Settings:\n"
        '    token = os.environ["QUEUE_TOKEN"]\n'  # class body, required
        '    bucket = os.environ.get("REPORT_BUCKET")\n',
        encoding="utf-8",
    )
    secret_value = "sk-live-" + "9z8Y7x6W" * 4  # check_secrets: fake
    (repo / ".env").write_text(
        f"QUEUE_HOST=queue.internal\nREPORT_BUCKET=\nUNUSED={secret_value}\n", encoding="utf-8"
    )
    (repo / ".env.example").write_text("QUEUE_TOKEN=\n", encoding="utf-8")
    workspace = create_workspace(repo, tmp_path / "ws", "")
    result = await CodeMapTool().run(CodeMapTool.Args(action="env"), ToolContext(workspace=workspace))
    text = result.content
    assert (
        "Read without a default and not set" in text and "QUEUE_TOKEN, REPORT_BUCKET" in text.splitlines()[0]
    )
    assert "env file .env: QUEUE_HOST, REPORT_BUCKET, UNUSED" in text and ".env.example" not in text
    assert "QUEUE_TOKEN: read in svc/settings.py:8 (no default); NOT SET in any env file" in text
    assert "REPORT_BUCKET: read in svc/settings.py:9 (no default); set but EMPTY in .env" in text
    assert "QUEUE_HOST: read in svc/settings.py:3 (no default); set in .env" in text
    assert "QUEUE_REGION: read in svc/settings.py:4 (has a default); NOT SET in any env file" in text
    assert secret_value not in text and "queue.internal" not in text  # names and states only, never a value


def test_environments_and_ignored_folders_are_not_indexed(tmp_path: Path) -> None:
    root, store = tmp_path / "repo", tmp_path / "store"
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    for name in ("libs", ".vendor", "generated"):
        (root / name).mkdir()
        (root / name / "lib.py").write_text("X = 1\n", encoding="utf-8")
    (root / "libs" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
    (root / ".gitignore").write_text("# comment\ngenerated/\n*.pyc\n", encoding="utf-8")
    structure, _ = refresh(root, store)
    assert list(structure["files"]) == ["app/main.py"]


def test_unchanged_files_are_neither_read_nor_parsed_again(tmp_path: Path, monkeypatch) -> None:
    from forge.knowledge import structure as structure_module

    root, store = tmp_path / "repo", tmp_path / "store"
    root.mkdir()
    for index in range(5):
        (root / f"m{index}.py").write_text(f"def f{index}():\n    return {index}\n", encoding="utf-8")
    refresh(root, store, keep=False)  # a copy that is only answered for: nothing stored
    parsed: list[str] = []
    real = structure_module._describe
    monkeypatch.setattr(
        structure_module, "_describe", lambda r, p, d: (parsed.append(p.name), real(r, p, d))[1]
    )
    _, report = refresh(root, store, keep=False)
    assert parsed == [] and len(report.added) == 5  # nothing stored, yet nothing parsed again
    (root / "m0.py").write_text("def f0():\n    return 'changed and longer'\n", encoding="utf-8")
    _, report = refresh(root, store, keep=False)
    assert parsed == ["m0.py"]


def test_installed_libraries_are_not_delivered(tmp_path: Path) -> None:
    from forge.workspace.ignore import IgnoreRules

    (tmp_path / "tools" / "pyvenv_home").mkdir(parents=True)
    (tmp_path / "tools" / "pyvenv_home" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
    rules = IgnoreRules(tmp_path)
    assert rules.is_ignored(".vendor", is_dir=True)
    assert rules.is_ignored("tools/pyvenv_home", is_dir=True)
    assert not rules.is_ignored("tools", is_dir=True)
