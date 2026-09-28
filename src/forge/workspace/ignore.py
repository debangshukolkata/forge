"""Which repository files are copied into a workspace (spec §6.1 step 3) and which are secret."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pathspec

# Always excluded, whatever .gitignore says. The app's venv is reused in place, never copied.
DEFAULT_EXCLUDES = [
    ".git/",
    ".hg/",
    ".svn/",
    ".venv/",
    "venv/",
    "env/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".tox/",
    "node_modules/",
    "dist/",
    "build/",
    "*.egg-info/",
    "logs/",
    ".forge/",
]

# Copied (the app needs them to run) but never shown to the LLM and never exported (spec §6.1).
SECRET_PATTERNS = [".env", ".env.*", "*.pem", "*.pfx", "*.p12", "*.key", "secrets/"]


class IgnoreRules:
    """Default excludes plus every .gitignore from the repository root down, with git's
    last-match-wins semantics (a deeper .gitignore can re-include what a parent excluded)."""

    def __init__(
        self,
        repo_root: Path,
        extra_excludes: list[str] | None = None,
        extra_secret_patterns: list[str] | None = None,
    ) -> None:
        self.repo_root = repo_root
        self._defaults = pathspec.GitIgnoreSpec.from_lines(DEFAULT_EXCLUDES + (extra_excludes or []))
        self._secrets = pathspec.GitIgnoreSpec.from_lines(SECRET_PATTERNS + (extra_secret_patterns or []))
        self._gitignores: dict[str, pathspec.GitIgnoreSpec | None] = {}

    def is_ignored(self, relative: str, is_dir: bool) -> bool:
        """relative: repository-root-relative POSIX path."""
        candidate = relative + "/" if is_dir else relative
        if self._defaults.match_file(candidate):
            return True
        ignored = False
        path = PurePosixPath(relative)
        for directory in [PurePosixPath("."), *reversed(path.parents[:-1])]:
            spec = self._gitignore_for(directory)
            if spec is None:
                continue
            inside = path.relative_to(directory).as_posix() if str(directory) != "." else relative
            result = spec.check_file(inside + "/" if is_dir else inside)
            if result.include is not None:
                ignored = result.include
        return ignored

    def is_secret(self, relative: str) -> bool:
        return bool(self._secrets.match_file(relative))

    def _gitignore_for(self, directory: PurePosixPath) -> pathspec.GitIgnoreSpec | None:
        key = directory.as_posix()
        if key not in self._gitignores:
            gitignore = self.repo_root / key / ".gitignore"
            self._gitignores[key] = (
                pathspec.GitIgnoreSpec.from_lines(
                    gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
                )
                if gitignore.is_file()
                else None
            )
        return self._gitignores[key]
