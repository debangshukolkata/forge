"""Builds a ready-to-run session from configuration: config + secrets -> router -> event bus -> host."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from forge.config import ForgeConfig, Secrets, forge_home, load_config, load_secrets
from forge.engine.events import EventBus, EventType
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.workspace.workspace import Workspace


def new_session_log_path(home: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return home / "sessions" / stamp / "events.jsonl"


def build_session(
    config: ForgeConfig | None = None,
    secrets: Secrets | None = None,
    log_path: Path | None = None,
    workspace: Workspace | None = None,
    orchestrated: bool = True,
) -> SessionHost:
    home = forge_home()
    config = config or load_config(home)
    secrets = secrets or load_secrets(home)
    if log_path is None:
        # With a workspace, the transcript lives in it (spec §6.2); otherwise in Forge home (D-029).
        log_path = (
            workspace.forge_dir / "transcripts" / "events.jsonl" if workspace else new_session_log_path(home)
        )
    bus = EventBus(log_path)

    async def on_notice(kind: str, data: dict[str, Any]) -> None:
        # Per-call usage is summarised by COST_UPDATED after each turn; retries/fallbacks are shown.
        if kind != "usage":
            await bus.publish(EventType.NOTICE, {"kind": kind, **data})

    router = LLMRouter(config, secrets, on_notice=on_notice)
    return SessionHost(
        router,
        bus,
        workspace=workspace,
        orchestrated=orchestrated and workspace is not None,
        secrets=secrets,
    )
