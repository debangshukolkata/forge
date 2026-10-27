from __future__ import annotations

import io
import json
from typing import Any

import pytest

from inventory_api import create_app


class Client:
    def __init__(self) -> None:
        self.app = create_app()

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        raw: bytes | None = None,
        content_type: str | None = "application/json",
        query: str = "",
    ) -> tuple[int, dict[str, str], Any, str]:
        payload = raw if raw is not None else (b"" if body is None else json.dumps(body).encode("utf-8"))
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "SERVER_NAME": "test",
            "SERVER_PORT": "80",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(payload),
            "wsgi.errors": io.StringIO(),
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "CONTENT_LENGTH": str(len(payload)) if payload else "",
        }
        if content_type is not None and (payload or method in ("POST", "PUT", "PATCH")):
            environ["CONTENT_TYPE"] = content_type
        seen: dict[str, Any] = {}

        def start_response(status: str, headers: list[tuple[str, str]], exc_info: Any = None) -> Any:
            seen["status"] = status
            seen["headers"] = headers

        chunks = self.app(environ, start_response)
        text = b"".join(chunks).decode("utf-8")
        status_text = seen["status"]
        assert status_text.split(" ", 1)[0].isdigit() and len(status_text.split(" ", 1)) == 2
        headers = {k.lower(): v for k, v in seen["headers"]}
        data = json.loads(text) if text else None
        return int(status_text.split()[0]), headers, data, text

    def create(self, name: str = "Bolt", quantity: int = 5, price: float = 1.5) -> dict[str, Any]:
        status, _, data, _ = self.call("POST", "/items", {"name": name, "quantity": quantity, "price": price})
        assert status == 201
        return data  # type: ignore[no-any-return]


def error_of(data: Any) -> dict[str, Any]:
    assert set(data) == {"error"}
    return data["error"]  # type: ignore[no-any-return]


def test_create_and_read_back() -> None:
    api = Client()
    status, headers, data, _ = api.call("POST", "/items", {"name": "  Bolt M4 ", "quantity": 7, "price": 0.25})
    assert status == 201
    assert data == {"id": 1, "name": "Bolt M4", "quantity": 7, "price": 0.25}
    assert headers["location"] == "/items/1"
    assert headers["content-type"] == "application/json"
    status, _, got, _ = api.call("GET", "/items/1")
    assert (status, got) == (200, data)


def test_quantity_defaults_to_zero_and_ids_grow_and_are_not_reused() -> None:
    api = Client()
    status, _, first, _ = api.call("POST", "/items", {"name": "a", "price": 1})
    assert status == 201 and first["quantity"] == 0 and first["id"] == 1
    api.create("b")
    assert api.call("DELETE", "/items/2")[0] == 204
    assert api.create("c")["id"] == 3


def test_apps_are_independent() -> None:
    one, two = Client(), Client()
    one.create("x")
    assert two.call("GET", "/items")[2]["total"] == 0


def test_delete_returns_empty_body_and_then_404() -> None:
    api = Client()
    api.create()
    status, headers, data, text = api.call("DELETE", "/items/1")
    assert (status, text, data) == (204, "", None)
    status, _, data, _ = api.call("GET", "/items/1")
    assert status == 404 and error_of(data)["code"] == "not_found"
    assert api.call("DELETE", "/items/1")[0] == 404


@pytest.mark.parametrize(
    "body, bad",
    [
        ({"quantity": 1, "price": 1}, {"name"}),
        ({"name": "x", "quantity": 1}, {"price"}),
        ({"name": "   ", "price": 1}, {"name"}),
        ({"name": "x" * 81, "price": 1}, {"name"}),
        ({"name": 5, "price": 1}, {"name"}),
        ({"name": "x", "price": -0.01}, {"price"}),
        ({"name": "x", "price": "3"}, {"price"}),
        ({"name": "x", "price": True}, {"price"}),
        ({"name": "x", "price": 1, "quantity": -1}, {"quantity"}),
        ({"name": "x", "price": 1, "quantity": 1.5}, {"quantity"}),
        ({"name": "x", "price": 1, "quantity": True}, {"quantity"}),
        ({"name": "x", "price": 1, "color": "red"}, {"color"}),
        ({"name": "x", "price": 1, "id": 9}, {"id"}),
        ({"name": "", "price": "no", "quantity": -3, "extra": 1}, {"name", "price", "quantity", "extra"}),
    ],
)
def test_validation_errors_list_every_bad_field(body: dict[str, Any], bad: set[str]) -> None:
    api = Client()
    status, headers, data, _ = api.call("POST", "/items", body)
    assert status == 400
    assert headers["content-type"] == "application/json"
    error = error_of(data)
    assert error["code"] == "validation_error" and isinstance(error["message"], str)
    assert set(error["details"]) == bad
    assert api.call("GET", "/items")[2]["total"] == 0


def test_name_of_80_characters_and_price_zero_are_fine() -> None:
    api = Client()
    status, _, data, _ = api.call("POST", "/items", {"name": "n" * 80, "price": 0})
    assert status == 201 and data["price"] == 0


def test_nan_and_infinity_are_rejected() -> None:
    api = Client()
    for text in (b'{"name": "x", "price": NaN}', b'{"name": "x", "price": Infinity}'):
        status, _, data, _ = api.call("POST", "/items", raw=text)
        assert status == 400
        assert error_of(data)["code"] in {"validation_error", "invalid_json"}
    assert api.call("GET", "/items")[2]["total"] == 0


def test_media_type_and_json_errors() -> None:
    api = Client()
    status, _, data, _ = api.call("POST", "/items", {"name": "x", "price": 1}, content_type="text/plain")
    assert status == 415 and error_of(data)["code"] == "unsupported_media_type"
    status, _, data, _ = api.call("POST", "/items", {"name": "x", "price": 1}, content_type=None)
    assert status == 415
    status, _, data, _ = api.call(
        "POST", "/items", {"name": "x", "price": 1}, content_type="Application/JSON; charset=utf-8"
    )
    assert status == 201
    for raw in (b"{oops", b"", b"[1, 2]", b'"text"', b"null", b"\xff\xfe"):
        status, _, data, _ = api.call("POST", "/items", raw=raw)
        assert status == 400 and error_of(data)["code"] == "invalid_json", raw


def test_conflict_is_case_insensitive_on_the_stripped_name() -> None:
    api = Client()
    api.create("Washer")
    status, _, data, _ = api.call("POST", "/items", {"name": " WASHER ", "price": 1})
    assert status == 409 and error_of(data)["code"] == "conflict"
    other = api.create("Nut")
    status, _, data, _ = api.call("PATCH", f"/items/{other['id']}", {"name": "washer"})
    assert status == 409
    status, _, data, _ = api.call("PUT", f"/items/{other['id']}", {"name": "NUT", "price": 2})
    assert status == 200 and data["name"] == "NUT"  # its own name is not a conflict


def test_put_replaces_and_patch_changes_only_sent_fields() -> None:
    api = Client()
    api.create("Bolt", 5, 1.5)
    status, _, data, _ = api.call("PUT", "/items/1", {"name": "Screw", "price": 2})
    assert (status, data) == (200, {"id": 1, "name": "Screw", "quantity": 0, "price": 2})
    status, _, data, _ = api.call("PATCH", "/items/1", {"quantity": 9})
    assert (status, data) == (200, {"id": 1, "name": "Screw", "quantity": 9, "price": 2})
    status, _, data, _ = api.call("PUT", "/items/1", {"name": "Screw"})
    assert status == 400 and set(error_of(data)["details"]) == {"price"}


def test_patch_rules() -> None:
    api = Client()
    api.create()
    status, _, data, _ = api.call("PATCH", "/items/1", {})
    assert status == 400 and error_of(data)["code"] == "validation_error"
    status, _, data, _ = api.call("PATCH", "/items/1", {"id": 5})
    assert status == 400 and "id" in error_of(data)["details"]
    status, _, data, _ = api.call("PATCH", "/items/1", {"price": -1})
    assert status == 400
    assert api.call("GET", "/items/1")[2]["price"] == 1.5  # a rejected patch changes nothing
    status, _, data, _ = api.call("PATCH", "/items/1", [1])
    assert status == 400 and error_of(data)["code"] == "invalid_json"


def test_order_of_checks_missing_item_before_body_problems() -> None:
    api = Client()
    status, _, data, _ = api.call("PUT", "/items/42", raw=b"{broken", content_type="text/plain")
    assert status == 404 and error_of(data)["code"] == "not_found"
    api.create()
    status, _, data, _ = api.call("PUT", "/items/1", raw=b"{broken", content_type="text/plain")
    assert status == 415
    status, _, data, _ = api.call("PUT", "/items/1", raw=b"{broken")
    assert status == 400 and error_of(data)["code"] == "invalid_json"


@pytest.mark.parametrize("path", ["/", "/item", "/items/", "/items/abc", "/items/0", "/items/-1", "/items/1/x", "/items/01"])
def test_unknown_paths_are_404(path: str) -> None:
    api = Client()
    api.create()
    status, headers, data, _ = api.call("GET", path)
    assert status == 404 and error_of(data)["code"] == "not_found"
    assert headers["content-type"] == "application/json"


def test_wrong_method_is_405_with_allow_header() -> None:
    api = Client()
    api.create()
    status, headers, data, _ = api.call("DELETE", "/items")
    assert status == 405 and headers["allow"] == "GET, POST" and error_of(data)["code"] == "method_not_allowed"
    status, headers, data, _ = api.call("POST", "/items/1", {"name": "z", "price": 1})
    assert status == 405 and headers["allow"] == "DELETE, GET, PATCH, PUT"
    assert api.call("PUT", "/items")[0] == 405


def fill(api: Client, count: int) -> None:
    for number in range(1, count + 1):
        api.create(f"item {number:02d}", number, number)


def test_list_defaults_and_pagination_numbers() -> None:
    api = Client()
    fill(api, 25)
    status, headers, data, _ = api.call("GET", "/items")
    assert status == 200 and headers["content-type"] == "application/json"
    assert (data["page"], data["per_page"], data["total"], data["pages"]) == (1, 10, 25, 3)
    assert [i["id"] for i in data["items"]] == list(range(1, 11))
    data = api.call("GET", "/items", query="page=3")[2]
    assert [i["id"] for i in data["items"]] == [21, 22, 23, 24, 25]
    data = api.call("GET", "/items", query="per_page=5&page=2")[2]
    assert [i["id"] for i in data["items"]] == [6, 7, 8, 9, 10] and data["pages"] == 5
    data = api.call("GET", "/items", query="page=9")[2]
    assert data["items"] == [] and data["total"] == 25 and data["page"] == 9


def test_list_exact_multiple_and_empty() -> None:
    api = Client()
    data = api.call("GET", "/items")[2]
    assert data == {"items": [], "page": 1, "per_page": 10, "total": 0, "pages": 0}
    fill(api, 20)
    data = api.call("GET", "/items", query="per_page=10")[2]
    assert data["pages"] == 2
    assert api.call("GET", "/items", query="per_page=100")[2]["pages"] == 1


def test_list_filter_by_name() -> None:
    api = Client()
    for name in ("Red Bolt", "blue bolt", "Washer", "BOLT cutter"):
        api.create(name)
    data = api.call("GET", "/items", query="q=bolt")[2]
    assert [i["name"] for i in data["items"]] == ["Red Bolt", "blue bolt", "BOLT cutter"]
    assert data["total"] == 3 and data["pages"] == 1
    data = api.call("GET", "/items", query="q=bolt&per_page=2&page=2")[2]
    assert [i["name"] for i in data["items"]] == ["BOLT cutter"] and data["pages"] == 2
    assert api.call("GET", "/items", query="q=zzz")[2]["pages"] == 0


@pytest.mark.parametrize(
    "query, bad",
    [
        ("page=0", {"page"}),
        ("page=-1", {"page"}),
        ("page=abc", {"page"}),
        ("page=1.5", {"page"}),
        ("page=", {"page"}),
        ("per_page=0", {"per_page"}),
        ("per_page=101", {"per_page"}),
        ("per_page=x&page=0", {"page", "per_page"}),
    ],
)
def test_bad_pagination_parameters(query: str, bad: set[str]) -> None:
    api = Client()
    api.create()
    status, _, data, _ = api.call("GET", "/items", query=query)
    assert status == 400
    assert error_of(data)["code"] == "validation_error" and set(error_of(data)["details"]) == bad


def test_per_page_100_is_allowed() -> None:
    api = Client()
    api.create()
    assert api.call("GET", "/items", query="per_page=100")[0] == 200


def test_unicode_names_round_trip() -> None:
    api = Client()
    status, _, data, _ = api.call("POST", "/items", {"name": "Schraube über ☃", "price": 1})
    assert status == 201
    assert api.call("GET", "/items/1")[2]["name"] == "Schraube über ☃"
    assert api.call("GET", "/items", query="q=%C3%9CBER")[2]["total"] == 1
