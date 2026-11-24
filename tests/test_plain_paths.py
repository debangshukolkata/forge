"""D-651: a path that repeats the folder it is in is corrected at the entrance, so logs and delivery have the right name."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.engine.session_host import SessionHost
from forge.llm.base import Message
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router, reply, responses_body, text_output


def test_only_a_clear_case_is_corrected(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    plain = workspace.plain_relative
    assert plain("repo/backend/new.py") == "backend/new.py"
    assert plain("repo\\backend\\new.py") == "backend/new.py"
    assert plain("backend/.forge/tool_outputs/a.txt") == ".forge/tool_outputs/a.txt"
    for same in ("backend/x.py", "repo", "repo/new_folder/x.py", "other/x.py", "repo/../x.py", "/repo/backend/x.py",
                 "C:/repo/backend/x.py", "project/x.py"):  # fmt: skip
        assert plain(same) == same, same
    (workspace.repo_dir / "repo").mkdir()
    assert plain("repo/backend/new.py") == "repo/backend/new.py"  # a real folder of that name


async def test_the_change_is_logged_and_delivered_under_the_right_name(
    original_repo: Path, tmp_path: Path
) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    call = {
        "type": "function_call", "id": "f1", "call_id": "c1", "name": "write_file", "status": "completed",
        "arguments": json.dumps({"path": "repo/backend/new_module.py", "content": "X = 1\n", "reason": "t"}),
    }  # fmt: skip
    answers = iter([responses_body([call]), responses_body([text_output("Done.")])])
    host = SessionHost(
        mocked_router(lambda request: reply(request, next(answers))),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    assert host.agent is not None
    host.agent.context.require_baseline = False

    async def no_delta(delta: str) -> None:
        return None

    with pytest.MonkeyPatch.context() as patch:

        async def no_review(context: object) -> None:
            return None

        patch.setattr("forge.agent.loop.review_leftovers", no_review)
        await host.agent.run([Message.system("s"), Message.user("write it")], no_delta)
    assert (workspace.repo_dir / "backend" / "new_module.py").is_file()
    assert not (workspace.repo_dir / "repo").exists()
    assert [change.path for change in workspace.changes()] == ["backend/new_module.py"]
