"""DB requests (spec §9.5.2): when Forge can't make a database change itself, it writes exact SQL for the
user or their DBA, keeps working on independent tasks, and verifies once they say it's done.

.forge/db_requests/DBR-<n>/request.sql, REQUEST.md, status.json
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from forge.workspace.workspace import Workspace

RequestStatus = Literal["pending", "done", "failed", "skipped", "cannot"]


class DbRequest(BaseModel):
    id: str
    title: str
    purpose: str
    target: str  # e.g. "local database forge_dev, schema forge_req_12"
    who: Literal["you", "your DBA"] = "you"
    sql: str
    verification_query: str
    status: RequestStatus = "pending"
    note: str = ""
    created: str = ""


class DbRequests:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.root = workspace.forge_dir / "db_requests"

    def create(
        self,
        title: str,
        purpose: str,
        target: str,
        sql: str,
        verification_query: str,
        who: Literal["you", "your DBA"] = "you",
    ) -> DbRequest:
        number = len(self.all()) + 1
        request = DbRequest(
            id=f"DBR-{number}",
            title=title,
            purpose=purpose,
            target=target,
            who=who,
            sql=sql,
            verification_query=verification_query,
            created=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        folder = self.workspace.jail.check(self.root / request.id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "request.sql").write_text(
            f"-- {request.id}: {title}\n-- Target: {target}\n\n{sql.strip()}\n", encoding="utf-8"
        )
        (folder / "REQUEST.md").write_text(self._markdown(request), encoding="utf-8")
        self._save(request)
        return request

    def all(self) -> list[DbRequest]:
        if not self.root.exists():
            return []
        requests = [
            DbRequest.model_validate_json((folder / "status.json").read_text(encoding="utf-8"))
            for folder in self.root.iterdir()
            if (folder / "status.json").exists()
        ]
        return sorted(requests, key=lambda r: int(r.id.split("-")[1]))

    def get(self, request_id: str) -> DbRequest | None:
        return next((r for r in self.all() if r.id.upper() == request_id.upper()), None)

    def set_status(self, request_id: str, status: RequestStatus, note: str = "") -> DbRequest:
        request = self.get(request_id)
        if request is None:
            raise KeyError(request_id)
        request.status, request.note = status, note
        self._save(request)
        return request

    def _save(self, request: DbRequest) -> None:
        path = self.workspace.jail.check(self.root / request.id / "status.json")
        path.write_text(request.model_dump_json(indent=1), encoding="utf-8")

    def folder(self, request_id: str) -> Path:
        return self.root / request_id

    @staticmethod
    def _markdown(request: DbRequest) -> str:
        return (
            f"# {request.id}: {request.title}\n\n"
            f"**Why:** {request.purpose}\n\n**Where:** {request.target}\n\n**Who runs it:** {request.who} "
            "(pgAdmin, DBeaver or psql all work)\n\n"
            f"## SQL (also in request.sql)\n\n```sql\n{request.sql.strip()}\n```\n\n"
            f"## How Forge checks it worked\n\n```sql\n{request.verification_query.strip()}\n```\n\n"
            "When it's done, tell Forge: `/db done " + request.id + "` (if Forge can't reach this database, "
            "add the verification query's result, column names only — never data rows). If you can't run it: "
            f"`/db cant {request.id} <why>`.\n"
        )
