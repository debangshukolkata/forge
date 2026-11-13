"""D-600: output that shows the database refused a write gets a note to use the scratch tools, not to patch the application."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from forge.agent.hints import (
    NAME_RESOLUTION_NOTE,
    READ_ONLY_DATABASE_NOTE,
    name_resolution_note,
    read_only_database_note,
)
from forge.agent.loop import AgentLoop

REFUSALS = [
    "psycopg.errors.InsufficientPrivilege: permission denied for table runs",
    "ERROR: permission denied for schema forge_x",
    "cannot execute INSERT in a read-only transaction",
    "sqlalchemy.exc.ProgrammingError: (psycopg2.errors.InsufficientPrivilege) must be owner of table agents",
]


@pytest.mark.parametrize("text", REFUSALS)
def test_a_refused_write_in_the_output_gets_the_note(text: str) -> None:
    note = read_only_database_note(
        "read_background", f"[running]\n{text}\n", already_on_scratch=False, given=0
    )
    assert note == READ_ONLY_DATABASE_NOTE and "db_copy_table" in note and "use_scratch_database" in note
    assert "Do not change the application" in note


def test_nothing_is_added_for_other_output_other_tools_or_after_the_switch_to_scratch() -> None:
    refusal = "permission denied for table runs"
    assert read_only_database_note("read_background", "all fine, 3 rows", False, 0) == ""
    assert (
        read_only_database_note("db_query", refusal, False, 0) == ""
    )  # the database tools report it themselves
    assert read_only_database_note("read_background", refusal, already_on_scratch=True, given=0) == ""
    assert (
        read_only_database_note("read_background", refusal, False, given=2) == ""
    )  # at most twice per session
    for tool in ("run_command", "python_run", "http_request", "monitor", "start_background"):
        assert read_only_database_note(tool, refusal, False, 0) == READ_ONLY_DATABASE_NOTE


def _loop(db: object) -> AgentLoop:
    loop = AgentLoop.__new__(AgentLoop)  # only the note is under test
    loop.context = SimpleNamespace(db=db)  # type: ignore[assignment]
    loop._database_notes = 0
    loop._network_notes = 0
    return loop


def test_the_loop_adds_the_note_twice_at_most_and_only_when_scratch_is_not_in_use() -> None:
    no_scratch = SimpleNamespace(scratch=object(), app_variables=lambda: {})
    loop = _loop(no_scratch)
    text = "psycopg.errors.InsufficientPrivilege: permission denied for table runs"
    assert loop._with_database_note("read_background", text).endswith(READ_ONLY_DATABASE_NOTE)
    assert loop._with_database_note("read_background", text).endswith(READ_ONLY_DATABASE_NOTE)
    assert loop._with_database_note("read_background", text) == text  # the third time nothing is added

    pointed = _loop(SimpleNamespace(scratch=object(), app_variables=lambda: {"DATABASE_URL": "url"}))
    assert (
        pointed._with_database_note("read_background", text) == text
    )  # the application already uses the scratch schema
    assert _loop(None)._with_database_note("read_background", text) == text  # no database in this project


UNRESOLVED = [
    "socket.gaierror: [Errno 11001] getaddrinfo failed",
    "httpx.ConnectError: [Errno -2] Name or service not known",
    "urllib3.exceptions.NameResolutionError: Failed to resolve 'nonprod.wisdomnext.eng'",
    "curl: (6) Could not resolve host: nonprod.wisdomnext.eng",
    "No such host is known.",
]


@pytest.mark.parametrize("text", UNRESOLVED)
def test_a_host_that_does_not_resolve_gets_the_network_note(text: str) -> None:
    """D-601: the likely cause is the VPN or the company DNS; the model says so first and does not hand the call to the user."""
    note = name_resolution_note("python_run", f"Traceback (most recent call last):\n{text}\n", given=0)
    assert note == NAME_RESOLUTION_NOTE and "VPN" in note and "by hand" in note


def test_the_network_note_is_for_running_tools_and_at_most_twice() -> None:
    text = "getaddrinfo failed"
    assert (
        name_resolution_note("read_file", text, 0) == ""
    )  # reading a file that says so is not a network failure
    assert name_resolution_note("run_command", "all fine", 0) == ""
    assert name_resolution_note("run_command", text, 2) == ""
    for tool in (
        "run_command",
        "python_run",
        "http_request",
        "read_background",
        "monitor",
        "start_background",
    ):
        assert name_resolution_note(tool, text, 1) == NAME_RESOLUTION_NOTE


def test_the_loop_adds_the_network_note_twice_at_most() -> None:
    loop = _loop(None)
    text = "ConnectError: [Errno 11001] getaddrinfo failed"
    assert loop._with_database_note("http_request", text).endswith(NAME_RESOLUTION_NOTE)
    assert loop._with_database_note("http_request", text).endswith(NAME_RESOLUTION_NOTE)
    assert loop._with_database_note("http_request", text) == text
