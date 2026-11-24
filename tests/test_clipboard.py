"""CP1: the timed clearing, without touching the real clipboard of the machine that runs the tests."""

from __future__ import annotations

import sys
import time

import pytest

from forge.toolkit import clipboard


class FakeUser:
    def __init__(self) -> None:
        self.number = 7
        self.emptied = 0

    def CreateWindowExW(self, *args: object) -> int:
        return 1

    def DestroyWindow(self, owner: object) -> int:
        return 1

    def OpenClipboard(self, owner: object) -> int:
        return 1

    def CloseClipboard(self) -> int:
        return 1

    def EmptyClipboard(self) -> int:
        self.emptied += 1
        self.number += 1
        return 1

    def GetClipboardSequenceNumber(self) -> int:
        return self.number

    def RegisterClipboardFormatW(self, name: str) -> int:
        return 50000 + len(name)


@pytest.fixture
def user(monkeypatch: pytest.MonkeyPatch) -> FakeUser:
    fake = FakeUser()
    monkeypatch.setattr(clipboard, "_api", lambda: (fake, None))
    fake.put = []  # type: ignore[attr-defined]
    monkeypatch.setattr(clipboard, "_put", lambda u, k, kind, data: fake.put.append((kind, data)) or True)  # type: ignore[attr-defined]
    return fake


def test_the_copy_is_marked_private_before_the_text_is_there(user: FakeUser) -> None:
    clipboard.copy_secret("abc")
    kinds = [kind for kind, _ in user.put]  # type: ignore[attr-defined]
    assert len(kinds) == 4 and kinds[-1] == clipboard.CF_UNICODETEXT
    assert user.put[-1][1] == "abc".encode("utf-16-le") + b"\0\0"  # type: ignore[attr-defined]


def test_it_is_cleared_after_the_time(user: FakeUser) -> None:
    clipboard.copy_for_a_minute("abc", 0.05)
    before = user.emptied
    time.sleep(0.4)
    assert user.emptied == before + 1


def test_something_copied_since_is_left_alone(user: FakeUser) -> None:
    clipboard.copy_for_a_minute("abc", 0.1)
    user.number += 1  # the user copied something else
    before = user.emptied
    time.sleep(0.5)
    assert user.emptied == before


def test_closing_debcraft_clears_a_copy_that_still_waits(user: FakeUser) -> None:
    clipboard.copy_for_a_minute("abc", 60)
    before = user.emptied
    clipboard.clear_now()
    assert user.emptied == before + 1


@pytest.mark.skipif(sys.platform == "win32", reason="checks the message on other systems")
def test_other_systems_get_a_clear_message() -> None:
    with pytest.raises(clipboard.ClipboardError, match="Windows only"):
        clipboard.copy_secret("abc")
