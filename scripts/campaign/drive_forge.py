"""Runs Forge on a workspace like `forge run --auto-approve`, but also approves `pip install` into the
workspace's own environment (always-ask, so plain headless mode refuses it). Logs every approval it grants.
Usage: python drive_forge.py <workspace> <prompt_file> <result_json>"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from forge.engine import headless
from forge.protocol.inputs import Approve
from forge.session import build_session
from forge.workspace.workspace import Workspace

WORKSPACE, PROMPT, RESULT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
GRANTED = WORKSPACE.parent / f"{WORKSPACE.name}_approvals.log"
original = headless.auto_reply


def policy(event, auto_approve):  # type: ignore[no-untyped-def]
    payload = event.payload
    if event.type.value == "approval_requested" and payload.get("always_ask"):
        command = str(payload.get("command") or payload.get("summary") or "")
        # Only package installs into the workspace's own venv; everything else stays refused.
        if re.search(r"\bpip3?\s+install\b|-m\s+pip\s+install\b", command) and "--target" not in command:
            with GRANTED.open("a", encoding="utf-8") as log:
                log.write(f"APPROVED: {command}\n")
            return Approve(request_id=payload["id"])
        with GRANTED.open("a", encoding="utf-8") as log:
            log.write(f"REFUSED: {command or payload.get('summary')}\n")
    return original(event, auto_approve)


async def main() -> int:
    headless.auto_reply = policy
    host = build_session(workspace=Workspace.open(WORKSPACE), orchestrated=True)
    result = await headless.run_headless(host, PROMPT.read_text(encoding="utf-8"), auto_approve=True)
    RESULT.write_text(
        json.dumps(
            {
                "exit_code": result.exit_code,
                "status": result.activity,
                "tasks": result.tasks,
                "errors": result.errors,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return result.exit_code


sys.exit(asyncio.run(main()))
