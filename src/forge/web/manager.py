"""The web UI's session manager: one active workspace session at a time (the engine runs in this process),
the list of recent workspaces, and who controls the session — only one client sends inputs, others watch
(spec §15A.2)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.engine.session_host import SessionHost
from forge.errors import ConversationBusyError, ConversationError
from forge.workspace.create import create_workspace
from forge.workspace.pyenv import find_app_folder_candidates
from forge.workspace.repo_memory import remembered_app_folder
from forge.workspace.workspace import Workspace

MAX_RECENT = 50
SessionFactory = Callable[[Workspace], SessionHost]


@dataclass
class WebSessionManager:
    home: Path
    session_factory: SessionFactory
    host: SessionHost | None = None
    workspace: Workspace | None = None
    controller: str | None = None
    sockets: dict[str, Any] = field(
        default_factory=dict, repr=False
    )  # client -> its websocket, to tell a window it now watches
    _runner: asyncio.Task[None] | None = field(default=None, repr=False)
    # The current phase label while new_workspace/new_standalone is running (spec: Home.tsx polls this
    # instead of showing one static "Setting up…" label for the whole call). Written from a worker thread
    # (asyncio.to_thread's callback) and only ever read back as a plain string, so no lock is needed.
    setup_progress: str | None = None

    # --- sessions ---

    async def open_workspace(self, path: Path) -> Workspace:
        workspace = Workspace.open(path)
        await self.close_session()
        self.workspace = workspace
        # Building a session reads the skills, the memory and the repository index (hundreds of files on a large
        # repository): on the event loop it froze every other request, the model list and the connection tests
        # included, until the project had opened.
        self.host = await asyncio.to_thread(self.session_factory, workspace)
        self._runner = asyncio.create_task(self.host.run())
        self._remember(workspace)
        return workspace

    # --- conversations of the open project (D-582) ---

    def conversations(self) -> dict[str, Any]:
        host = self.host
        if host is None or host.conversations is None:
            return {"active": None, "conversations": []}
        active = host.conversations.conversation_id
        return {
            "active": active,
            "conversations": [
                {**c.model_dump(), "active": c.id == active, "running": c.id == active and host.busy}
                for c in host.conversations.store.list()
            ],
        }

    async def switch_conversation(
        self, conversation_id: str | None, title: str = "", stop_running: bool = False
    ) -> str:
        """Opens another conversation of the project, or a new one when `conversation_id` is None. A running
        turn is stopped only when the caller said so (the UI asks first); its history up to the last finished
        step is saved before the project is opened again."""
        host, workspace = self.host, self.workspace
        if host is None or workspace is None or host.conversations is None:
            raise ConversationError("No project is open.")
        if host.busy:
            if not stop_running:
                raise ConversationBusyError("DebCraft is working in this conversation.")
            await host.interrupt()
            for _ in range(100):  # up to 10 seconds for the turn to end
                if not host.busy:
                    break
                await asyncio.sleep(0.1)
            else:
                raise ConversationError("DebCraft could not be stopped in time; nothing was switched.")
        await host.save_conversation(force=True)
        store = host.conversations.store
        chosen = store.create(title) if conversation_id is None else store.activate(conversation_id)
        await self.open_workspace(workspace.root)
        return chosen.id

    def rename_conversation(self, conversation_id: str, title: str) -> None:
        host = self.host
        if host is None or host.conversations is None:
            raise ConversationError("No project is open.")
        host.conversations.store.rename(conversation_id, title)

    async def new_workspace(
        self, repo: Path, path: Path, app_folder: str | None, project: str = ""
    ) -> Workspace:
        if not repo.is_dir():
            raise ValueError(f"{repo} is not a folder")
        folder = app_folder or remembered_app_folder(self.home, repo)
        if folder is None:
            candidates = find_app_folder_candidates(repo)
            if len(candidates) != 1:
                raise ValueError(
                    f"Which folder is the Python app? Candidates: {', '.join(candidates) or 'none found'}."
                )
            folder = candidates[0]
        self.setup_progress = "Copying the repository…"
        try:
            workspace = await asyncio.to_thread(
                create_workspace, repo, path, folder, on_progress=self._on_copy_progress
            )
        finally:
            self.setup_progress = None
        _set_project(workspace, project)
        return await self.open_workspace(workspace.root)

    def _on_copy_progress(self, count: int, current: str) -> None:
        self.setup_progress = f"Copying the repository… ({count} file{'s' if count != 1 else ''}: {current})"

    async def new_standalone(self, path: Path, profile_name: str, project: str = "") -> Workspace:
        """Mode B: no repository; the host profile describes the host."""
        from forge.modeb.profile import ProfileStore
        from forge.modeb.workspace import create_standalone_workspace

        profile = ProfileStore(self.home).open(profile_name)
        self.setup_progress = "Setting up the project…"
        try:
            workspace = await asyncio.to_thread(
                create_standalone_workspace, path, profile, None, self._set_setup_progress
            )
        finally:
            self.setup_progress = None
        _set_project(workspace, project)
        return await self.open_workspace(workspace.root)

    def _set_setup_progress(self, phase: str) -> None:
        self.setup_progress = phase

    async def close_session(self) -> None:
        if self.host is not None:
            await self.host.close()
        if self._runner is not None:
            self._runner.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._runner
        self.host, self.workspace, self._runner, self.controller = None, None, None, None

    # --- control: one client sends inputs, the rest watch ---

    def claim_control(self, client: str, take_over: bool = False) -> bool:
        if self.controller is None or self.controller == client or take_over:
            self.controller = client
            return True
        return False

    def release(self, client: str) -> None:
        if self.controller == client:
            self.controller = None

    # --- recent workspaces ---

    @property
    def _recent_file(self) -> Path:
        return self.home / "recent_workspaces.json"

    def recent(self) -> list[dict[str, Any]]:
        try:
            entries: list[dict[str, Any]] = json.loads(self._recent_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [e for e in entries if (Path(e["path"]) / ".forge" / "workspace.json").exists()]

    async def delete_project(self, path: Path) -> None:
        from forge.web.project_delete import check_deletable, remove_project_folder

        known = self.recent()
        check_deletable(path, self.home, known)
        if self.workspace is not None and self.workspace.root.resolve() == path.resolve():
            await self.close_session()  # release the event log and any running commands first
        await asyncio.to_thread(remove_project_folder, path.resolve())
        kept = [e for e in known if Path(e["path"]).resolve() != path.resolve()]
        self._recent_file.write_text(json.dumps(kept, indent=1), encoding="utf-8")

    def _remember(self, workspace: Workspace) -> None:
        entry = {
            "path": str(workspace.root),
            "name": workspace.info.project or workspace.info.name,
            "repo": workspace.info.repo_path or "standalone (Mode B)",
            "app_folder": workspace.info.app_subfolder,
        }
        entries = [entry, *[e for e in self.recent() if e["path"] != entry["path"]]][:MAX_RECENT]
        self._recent_file.parent.mkdir(parents=True, exist_ok=True)
        self._recent_file.write_text(json.dumps(entries, indent=1), encoding="utf-8")


def _set_project(workspace: Workspace, project: str) -> None:
    if project:
        workspace.info.project = project
        workspace.save_info()
