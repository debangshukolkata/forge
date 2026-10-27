Create `inventory_api.py`: a small REST API for stock items, written with the standard library only (no web framework, no packages, no sockets needed). It exposes `create_app()`, which returns a **WSGI application** (a callable `app(environ, start_response)`) with its own empty in-memory store. Two calls to `create_app()` give two independent apps. All bodies, in and out, are JSON (UTF-8).

**Item** `{"id": int, "name": str, "quantity": int, "price": number}`
- `name`: a string; leading and trailing spaces are stripped and the stored name is the stripped one; 1 to 80 characters after stripping.
- `quantity`: an integer >= 0 (a boolean is not an integer); optional, default 0.
- `price`: an int or float >= 0 (a boolean is not a number; NaN and Infinity are invalid); required.
- Names are unique, compared case-insensitively on the stripped name.
- Ids start at 1, grow by 1, and are never reused after a delete.

**Routes** (anything else is a 404; a path like `/items/abc`, `/items/0` or `/items/` is a 404 too)
- `POST /items` creates an item: status 201, the item as body, a `Location: /items/<id>` header. Unknown fields in the body are an error.
- `GET /items` lists items ordered by id: status 200, body `{"items": [...], "page": p, "per_page": n, "total": t, "pages": k}`. Query parameters: `page` (default 1, integer >= 1), `per_page` (default 10, integer 1 to 100), and `q` (optional; keep only items whose name contains `q`, case-insensitive; `total` and `pages` count the filtered items). `pages` is `ceil(total / per_page)`, 0 when nothing matches. A page past the end is a 200 with an empty `items` list. A bad `page` or `per_page` is a validation error.
- `GET /items/<id>` returns the item (200) or 404.
- `PUT /items/<id>` replaces the item: the same rules as POST (so an omitted `quantity` becomes 0); 200 with the item.
- `PATCH /items/<id>` changes only the fields sent; the body must contain at least one field and only known fields (`name`, `quantity`, `price`; `id` is not changeable); 200 with the item.
- `DELETE /items/<id>` returns 204 with an empty body, or 404.
- A known path with the wrong method is 405 with an `Allow` header listing the allowed methods, comma and space separated, sorted (`/items`: `GET, POST`; `/items/<id>`: `DELETE, GET, PATCH, PUT`).

**Errors** are JSON with `Content-Type: application/json` and the shape `{"error": {"code": "...", "message": "..."}}`. Validation errors also carry `"details"` inside the `error` object: `{"<field or parameter>": "<what is wrong>"}` listing every bad field at once, not only the first. Codes and statuses:
- `not_found` 404, `method_not_allowed` 405
- `unsupported_media_type` 415: POST, PUT and PATCH need a `Content-Type` whose media type is `application/json` (parameters such as `; charset=utf-8` are fine; a missing header is not)
- `invalid_json` 400: the body is not valid JSON, or is JSON but not an object
- `validation_error` 400: a field or query parameter is invalid, an unknown field is sent, or a required field is missing
- `conflict` 409: the name is already used by another item (an update that keeps the item's own name is not a conflict)

Order of checks: route, method, item exists (404), content type (415), JSON (400 `invalid_json`), field validation (400), name conflict (409).

Success responses also carry `Content-Type: application/json` (not the 204). Write tests for it too (`test_inventory_api.py`); they must call the WSGI callable directly. Use only the standard library.
