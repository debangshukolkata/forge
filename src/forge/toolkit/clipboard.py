"""Puts a secret on the Windows clipboard for a short time (CP1, D-645).

The user clicks a button; DebCraft's own process does the copying, so the value never passes through the browser.
Windows is asked to keep it out of the clipboard history and the cloud clipboard. It is cleared after a minute
unless something else was copied meanwhile."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from typing import Any

CLEAR_AFTER_S = 60
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
# Formats Windows and clipboard managers look for; a DWORD of 0 means "no".
EXCLUDED = "ExcludeClipboardContentFromMonitorProcessing"
NO_HISTORY = "CanIncludeInClipboardHistory"
NO_CLOUD = "CanUploadToCloudClipboard"


class ClipboardError(Exception):
    """The clipboard cannot be used here, with the reason for the user."""


def _api() -> tuple[Any, Any]:
    if sys.platform != "win32":
        raise ClipboardError("Copying works on Windows only.")
    user, kernel = (
        ctypes.WinDLL("user32", use_last_error=True),
        ctypes.WinDLL("kernel32", use_last_error=True),
    )
    kernel.GlobalAlloc.restype = kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel.GlobalLock.argtypes = kernel.GlobalUnlock.argtypes = kernel.GlobalFree.argtypes = [ctypes.c_void_p]
    user.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user.SetClipboardData.restype = ctypes.c_void_p
    user.OpenClipboard.argtypes = [ctypes.c_void_p]
    user.CreateWindowExW.restype = ctypes.c_void_p
    user.CreateWindowExW.argtypes = [
        ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
        *[ctypes.c_int] * 4, *[ctypes.c_void_p] * 4,
    ]  # fmt: skip
    user.DestroyWindow.argtypes = [ctypes.c_void_p]
    user.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
    return user, kernel


def _owner(user: Any) -> Any:
    """A hidden window: Windows may refuse data from a program that opened the clipboard without an owner."""
    return user.CreateWindowExW(0, "STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)


def _open(user: Any) -> Any:
    owner = _owner(user)
    for _ in range(20):  # another program may hold it for a moment
        if user.OpenClipboard(owner):
            return owner
        time.sleep(0.05)
    denied = getattr(ctypes, "get_last_error", lambda: 0)() == 5
    user.DestroyWindow(owner)
    raise ClipboardError(
        "Windows does not let DebCraft use the clipboard here."
        if denied
        else "Another program is using the clipboard. Try again."
    )


def _close(user: Any, owner: Any) -> None:
    user.CloseClipboard()
    user.DestroyWindow(owner)


def _put(user: Any, kernel: Any, kind: int, data: bytes) -> bool:
    handle = kernel.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        return False
    place = kernel.GlobalLock(handle)
    ctypes.memmove(place, data, len(data))
    kernel.GlobalUnlock(handle)
    if user.SetClipboardData(kind, handle):
        return True  # the system owns the memory now
    kernel.GlobalFree(handle)
    return False


def copy_secret(text: str) -> int:
    """Copies; returns the clipboard's sequence number, which changes with every later copy."""
    user, kernel = _api()
    owner = _open(user)
    try:
        user.EmptyClipboard()
        for name in (EXCLUDED, NO_HISTORY, NO_CLOUD):  # before the text, so no monitor sees it without them
            _put(user, kernel, user.RegisterClipboardFormatW(name), (0).to_bytes(4, "little"))
        if not _put(user, kernel, CF_UNICODETEXT, text.encode("utf-16-le") + b"\0\0"):
            raise ClipboardError("Windows did not accept the copy.")
    finally:
        _close(user, owner)
    return int(user.GetClipboardSequenceNumber())


def clear_if_unchanged(number: int) -> bool:
    """Empties the clipboard when nothing was copied since `copy_secret` returned this number."""
    user, _ = _api()
    owner = _open(user)
    try:
        if int(user.GetClipboardSequenceNumber()) != number:
            return False
        user.EmptyClipboard()
        return True
    finally:
        _close(user, owner)


def _clear_quietly(number: int) -> None:
    for _ in range(5):
        try:
            clear_if_unchanged(number)
            return
        except ClipboardError:
            time.sleep(1)


_waiting: threading.Timer | None = None
_waiting_number: int | None = None


def copy_for_a_minute(text: str, seconds: float = CLEAR_AFTER_S) -> None:
    global _waiting, _waiting_number
    number = copy_secret(text)
    if _waiting is not None:
        _waiting.cancel()
    _waiting = threading.Timer(seconds, _clear_quietly, (number,))
    _waiting.daemon = True
    _waiting_number = number
    _waiting.start()


def clear_now() -> None:
    """When DebCraft closes: a copy that is still waiting to be cleared does not outlive it."""
    global _waiting, _waiting_number
    if _waiting is not None and _waiting_number is not None and _waiting.is_alive():
        _waiting.cancel()
        _clear_quietly(_waiting_number)
    _waiting, _waiting_number = None, None
