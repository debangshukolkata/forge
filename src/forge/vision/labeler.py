"""The labelling helper (spec §13A.2): `forge label <eval-dir>` serves a single page on 127.0.0.1 where the
user draws boxes, types field values and marks unreadable fields per sample; labels are saved to
labels/<stem>.json.
Same security as the web UI (loopback only, session token, Host/Origin checks, strict CSP). Labels pre-filled
by a model are marked "unverified" until the user saves them."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from forge.safety.server_security import ServerSecurity

STATIC = Path(str(resources.files("forge.vision") / "static"))
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def create_label_app(eval_dir: Path, security: ServerSecurity) -> FastAPI:
    samples_dir, labels_dir = eval_dir / "samples", eval_dir / "labels"
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        problem = security.check(request.headers, request.cookies, request.query_params.get("t"))
        if problem is not None:
            return JSONResponse({"error": f"Forbidden: {problem}"}, status_code=403)
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = security.content_security_policy()
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def sample_path(name: str) -> Path:
        path = (samples_dir / name).resolve()
        if (
            path.parent != samples_dir.resolve()
            or path.suffix.lower() not in IMAGE_SUFFIXES
            or not path.is_file()
        ):
            raise HTTPException(404, "No such sample")
        return path

    @app.get("/")
    async def index(request: Request) -> Response:
        if request.query_params.get("t"):
            redirect = RedirectResponse("/", status_code=303)
            redirect.set_cookie(
                security.cookie_name, security.token, httponly=True, samesite="strict", path="/"
            )
            return redirect
        return FileResponse(STATIC / "label.html", media_type="text/html")

    @app.get("/label.js")
    async def script() -> Response:
        return FileResponse(STATIC / "label.js", media_type="text/javascript")

    @app.get("/api/samples")
    async def samples() -> list[dict[str, Any]]:
        result = []
        for path in sorted(p for p in samples_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES):
            label_path = labels_dir / f"{path.stem}.json"
            label = json.loads(label_path.read_text(encoding="utf-8")) if label_path.exists() else None
            result.append({"name": path.name, "label": label})
        return result

    @app.get("/sample/{name}")
    async def sample(name: str) -> Response:
        return FileResponse(sample_path(name))

    @app.post("/api/labels/{name}")
    async def save(name: str, request: Request) -> dict[str, bool]:
        sample_path(name)
        body = await request.json()
        label = {
            "sample": name,
            "fields": body.get("fields") or {},
            "regions": [
                {"label": str(r["label"]), "page": int(r.get("page", 1)), "box": [float(v) for v in r["box"]]}
                for r in body.get("regions") or []
                if len(r.get("box", [])) == 4
            ],
            "unreadable": [str(u) for u in body.get("unreadable") or []],
            "verified": True,  # saved by the user
            "sensitive": bool(body.get("sensitive", True)),
        }
        labels_dir.mkdir(parents=True, exist_ok=True)
        (labels_dir / f"{Path(name).stem}.json").write_text(json.dumps(label, indent=1), encoding="utf-8")
        return {"ok": True}

    return app
