"""Local history (spec §13B): when git is available, the workspace's code copy gets its own git history,
committed after every completed task (message = task id + title). The git directory lives in
.forge/history.git (never inside repo/ or project/, so nothing git-related is copied or exported), and git
never runs in the user's original repository. Secret files are excluded. Without git, the checkpoint system
gives the same undo/rewind features."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from forge.workspace.workspace import Workspace

GIT_TIMEOUT_S = 60


class History:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.git_dir = workspace.forge_dir / "history.git"
        self.available = shutil.which("git") is not None

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["git", f"--git-dir={self.git_dir}", f"--work-tree={self.workspace.repo_dir}", *args]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            encoding="utf-8",
            errors="replace",
            env={**__import__("os").environ, "GIT_TERMINAL_PROMPT": "0"},
        )

    def ensure(self) -> bool:
        if not self.available:
            return False
        if not (self.git_dir / "HEAD").exists():
            if self._git("init", "--quiet").returncode != 0:
                return False
            self._git("config", "user.name", "Forge")
            self._git("config", "user.email", "forge@localhost")
            self._git("config", "core.autocrlf", "false")
            self._write_excludes()
            self._git("add", "--all")
            self._git("commit", "--quiet", "--allow-empty", "-m", "baseline (workspace created)")
        return True

    def _write_excludes(self) -> None:
        secret = [path for path, entry in self.workspace.manifest.files.items() if entry.secret]
        patterns = ["venv/", ".venv/", "__pycache__/", "*.pyc", ".pytest_cache/", *secret]
        info = self.git_dir / "info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "exclude").write_text("\n".join(patterns) + "\n", encoding="utf-8")

    def commit(self, message: str) -> str | None:
        """Commits everything changed since the last commit; returns the short hash, or None if nothing."""
        if not self.ensure():
            return None
        self._git("add", "--all")
        if self._git("diff", "--cached", "--quiet").returncode == 0:
            return None
        if self._git("commit", "--quiet", "-m", message).returncode != 0:
            return None
        return self._git("rev-parse", "--short", "HEAD").stdout.strip() or None

    def log(self, limit: int = 30) -> str:
        if not self.ensure():
            return "git is not available: use /checkpoints."
        return (
            self._git("log", f"-{limit}", "--pretty=format:%h  %ad  %s", "--date=short").stdout
            or "No history."
        )

    def diff(self, ref: str) -> str:
        """The change a task made: `ref` is a commit hash or a task id (matched in the commit message)."""
        if not self.ensure():
            return "git is not available: use /checkpoints and the Diffs view."
        commit = ref
        if not all(c in "0123456789abcdef" for c in ref.lower()):
            found = self._git("log", "--pretty=format:%h", f"--grep=^{ref}\\b", "-1").stdout.strip()
            if not found:
                return f"No commit for {ref}."
            commit = found
        return self._git("show", "--stat", "--patch", commit).stdout[:60_000] or f"No commit {ref}."

    @property
    def root(self) -> Path:
        return self.workspace.repo_dir
