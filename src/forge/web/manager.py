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
from forge.workspace.create import create_workspace
from forge.workspace.pyenv import find_app_folder_candidates
from forge.workspace.repo_memory import remembered_app_folder
from forge.workspace.workspace import Workspace

MAX_RECENT = 12
SessionFactory = Callable[[Workspace], SessionHost]


@dataclass
class WebSessionManager:
    home: Path
    session_factory: SessionFactory
    host: SessionHost | None = None
    workspace: Workspace | None = None
    controller: str | None = None
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
        self.host = self.session_factory(workspace)
        self._runner = asyncio.create_task(self.host.run())
        self._remember(workspace)
        return workspace

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
