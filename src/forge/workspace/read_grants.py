"""Read-only access to places outside the workspace that the user has opened up (D-208).

Two kinds: folders that are always readable (the installed skills) and folders or files the user granted for
this project, with everything under a folder included. Only the user's own actions grant (the /allow-read
command, a path they type or @-mention); the model has no way to. The list is stored under the Forge home,
outside every folder a tool may write to, so the model cannot add to it either. Reading only: writes stay
inside the workspace jail whatever is granted."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from forge.errors import ForgeError
from forge.safety.paths import is_within, real_path


class ReadGrantError(ForgeError):
    """The path cannot be granted (missing, or too broad, or Forge's own folder)."""


class ReadGrants:
    def __init__(
        self,
        store: Path | None = None,
        always: list[Path] | None = None,
        protected_home: Path | None = None,
    ) -> None:
        self._store = store
        self._always = [real_path(path) for path in always or []]
        self._protected_home = real_path(protected_home) if protected_home else None

    @classmethod
    def none(cls) -> ReadGrants:
        """No grants at all: what a workspace has until a session attaches the real ones."""
        return cls()

    @classmethod
    def for_workspace(cls, workspace_root: Path, home: Path) -> ReadGrants:
        key = hashlib.sha1(os.path.normcase(str(real_path(workspace_root))).encode("utf-8")).hexdigest()[:16]
        return cls(home / "read_grants" / f"{key}.json", always=[home / "skills"], protected_home=home)

    # --- reading the list ---

    def granted(self) -> list[Path]:
        if self._store is None or not self._store.is_file():
            return []
        try:
            data = json.loads(self._store.read_text(encoding="utf-8"))
            return [Path(text) for text in data.get("paths", []) if isinstance(text, str)]
        except (OSError, ValueError, AttributeError):
            return []  # a damaged file grants nothing

    def roots(self) -> list[Path]:
        return [*self._always, *(path for path in self.granted() if path.exists())]

    def allows(self, resolved: Path) -> bool:
        return any(is_within(resolved, root) for root in self.roots())

    # --- changing it (only ever called for the user's own request) ---

    def grant(self, raw: str) -> Path:
        if self._store is None:
            raise ReadGrantError("Read grants are not available in this session.")
        text = raw.strip().strip("'\"")
        candidate = Path(text).expanduser()
        if not text or not candidate.is_absolute():
            raise ReadGrantError(f"Give the full path of a file or folder (got {raw!r}).")
        if not candidate.exists():
            raise ReadGrantError(f"{candidate} does not exist.")
        resolved = real_path(candidate)
        self._refuse_too_broad(resolved)
        current = self.granted()
        if not any(is_within(resolved, root) for root in current):
            current = [root for root in current if not is_within(root, resolved)] + [resolved]
            self._save(current)
        return resolved

    def revoke(self, raw: str) -> bool:
        text = raw.strip().strip("'\"")
        target = real_path(Path(text).expanduser()) if text else None
        current = self.granted()
        kept = [
            root
            for root in current
            if target is None or os.path.normcase(str(root)) != os.path.normcase(str(target))
        ]
        if len(kept) == len(current):
            return False
        self._save(kept)
        return True

    def _refuse_too_broad(self, resolved: Path) -> None:
        if resolved.parent == resolved:
            raise ReadGrantError("A whole drive cannot be granted; pick a folder.")
        if is_within(Path.home(), resolved):
            raise ReadGrantError(f"{resolved} holds your whole profile; pick a folder inside it.")
        home = self._protected_home
        if home is not None and is_within(home, resolved):
            raise ReadGrantError("Forge's own folder holds keys and accounts and cannot be granted.")
        if (
            home is not None
            and is_within(resolved, home)
            and not any(is_within(resolved, a) for a in self._always)
        ):
            raise ReadGrantError("Forge's own folder holds keys and accounts and cannot be granted.")

    def _save(self, paths: list[Path]) -> None:
        assert self._store is not None
        self._store.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._store.with_suffix(".tmp")
        temporary.write_text(json.dumps({"paths": [str(path) for path in paths]}, indent=1), encoding="utf-8")
        temporary.replace(self._store)
