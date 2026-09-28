"""Low-integrity sandbox for shell commands (DECISIONS D-049, D-050). Windows only, no admin needed.

A process running at LOW integrity may read everything but can only write to objects labelled low.
Forge labels just the workspace's repo/ copy and its scratch folders low, so a command that slips past
the classifier still cannot write to the user's original repository, their profile, or Forge's own
state (.forge/permissions.json, checkpoints, baseline, output/). Uses documented Win32 calls only.

SandboxedProcess mimics the parts of asyncio.subprocess.Process that Forge uses (pid, returncode,
stdout, wait), so the PowerShell runner treats both kinds of process the same way.
"""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import functools
import os
import re
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any

LOW_INTEGRITY_SID = "S-1-16-4096"
STILL_ACTIVE = 259
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000
_STARTF_USESTDHANDLES = 0x00000100


class SandboxUnavailableError(OSError):
    """Labelling or low-integrity process creation failed; the caller falls back and warns."""


def is_supported() -> bool:
    return sys.platform == "win32"


def label_low(folder: Path) -> None:
    """Marks a folder (and everything in and below it, now and later) as writable at low integrity."""
    folder.mkdir(parents=True, exist_ok=True)
    # Changing a mandatory label needs WRITE_OWNER, which inherited "Modify" rights (e.g. under C:\Work on
    # an enterprise laptop) don't give; %TEMP% gives Full control, which hid this. The user owns Forge's
    # own workspace folders, so they may grant themselves Full control there first.
    _icacls(folder, "/grant", f"*{_current_user_sid()}:(OI)(CI)F")  # the folder only: children inherit it
    # /T /C labels what it can; single items in use may fail, as before. What matters is the folder itself:
    # everything created in it later inherits the label, and icacls /C exits 0 even when items failed.
    _icacls(folder, "/setintegritylevel", "(OI)(CI)low", "/T", "/C", "/Q")
    if not has_low_label(folder):
        raise SandboxUnavailableError(f"the low-integrity label did not stick on {folder}")


def has_low_label(folder: Path) -> bool:
    shown = subprocess.run(["icacls", str(folder)], capture_output=True, text=True, timeout=60, check=False)
    return "Low Mandatory Level" in shown.stdout


def _icacls(folder: Path, *arguments: str) -> None:
    result = subprocess.run(
        ["icacls", str(folder), *arguments], capture_output=True, text=True, timeout=600, check=False
    )
    if result.returncode != 0:
        raise SandboxUnavailableError(
            f"icacls {arguments[0]} failed on {folder}: {(result.stdout + result.stderr).strip()[-300:]}"
        )


def _current_user_sid() -> str:
    result = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=30, check=False
    )
    match = re.search(r"S-1-[\d-]+", result.stdout)
    if not match:
        raise SandboxUnavailableError("could not determine the current user's SID")
    return match.group(0)


class SandboxedProcess:
    def __init__(self, pid: int, process_handle: int, stdout: asyncio.StreamReader) -> None:
        self.pid = pid
        self._handle = process_handle
        self.stdout = stdout
        self._returncode: int | None = None

    @property
    def returncode(self) -> int | None:
        if self._returncode is None:
            code = _exit_code(self._handle)
            if code != STILL_ACTIVE:
                self._returncode = code
                close_process_handle(self._handle)
        return self._returncode

    async def wait(self) -> int:
        while self.returncode is None:
            await asyncio.sleep(0.05)
        assert self._returncode is not None
        return self._returncode


async def spawn_low_integrity(argv: list[str], cwd: Path, env: dict[str, str]) -> SandboxedProcess:
    """Starts argv at low integrity with stdout+stderr piped and stdin at NUL."""
    if not is_supported():
        raise SandboxUnavailableError("the low-integrity sandbox exists only on Windows")
    import msvcrt  # Windows-only module

    read_fd, write_fd = os.pipe()
    null_fd = os.open(os.devnull, os.O_RDONLY)
    try:
        write_handle = msvcrt.get_osfhandle(write_fd)
        null_handle = msvcrt.get_osfhandle(null_fd)
        os.set_handle_inheritable(write_handle, True)
        os.set_handle_inheritable(null_handle, True)
        pid, process_handle = _create_low_process(
            subprocess.list2cmdline(argv), str(cwd), env, null_handle, write_handle
        )
    except OSError as error:
        os.close(read_fd)
        raise SandboxUnavailableError(f"could not start a low-integrity process: {error}") from error
    finally:
        os.close(write_fd)  # the child holds its own copy; closing ours lets the reader see EOF
        os.close(null_fd)

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=1 << 20)

    def pump() -> None:
        with os.fdopen(read_fd, "rb", buffering=0) as pipe:
            while block := pipe.read(65536):
                loop.call_soon_threadsafe(reader.feed_data, block)
        loop.call_soon_threadsafe(reader.feed_eof)

    threading.Thread(target=pump, name=f"forge-sandbox-{pid}", daemon=True).start()
    return SandboxedProcess(pid, process_handle, reader)


# --- Win32 plumbing (ctypes; module-level definitions are harmless on other platforms) ---


class _SidAndAttributes(ctypes.Structure):
    _fields_ = (("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD))


class _StartupInfo(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    )


class _ProcessInformation(ctypes.Structure):
    _fields_ = (
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    )


@functools.lru_cache(maxsize=1)
def _libraries() -> tuple[Any, Any]:
    """advapi32 and kernel32 with argument types declared (64-bit handles must not be truncated)."""
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle, dword, pointer, void_p = wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER, ctypes.c_void_p
    kernel32.GetCurrentProcess.restype = handle
    kernel32.GetExitCodeProcess.argtypes = [handle, pointer(dword)]
    kernel32.CloseHandle.argtypes = [handle]
    kernel32.LocalFree.argtypes = [void_p]
    advapi32.OpenProcessToken.argtypes = [handle, dword, pointer(handle)]
    advapi32.DuplicateTokenEx.argtypes = [handle, dword, void_p, ctypes.c_int, ctypes.c_int, pointer(handle)]
    advapi32.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, pointer(void_p)]
    advapi32.GetLengthSid.argtypes = [void_p]
    advapi32.SetTokenInformation.argtypes = [handle, ctypes.c_int, void_p, dword]
    advapi32.CreateProcessAsUserW.argtypes = [
        handle,
        wintypes.LPCWSTR,
        ctypes.c_wchar_p,
        void_p,
        void_p,
        wintypes.BOOL,
        dword,
        void_p,
        wintypes.LPCWSTR,
        void_p,
        void_p,
    ]
    return advapi32, kernel32


def _check(ok: int) -> None:
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


def _low_integrity_token() -> Any:
    advapi32, kernel32 = _libraries()
    token, low = wintypes.HANDLE(), wintypes.HANDLE()
    # TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT
    _check(
        advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x2 | 0x8 | 0x1 | 0x80, ctypes.byref(token))
    )
    try:
        # MAXIMUM_ALLOWED, SecurityImpersonation, TokenPrimary
        _check(advapi32.DuplicateTokenEx(token, 0x02000000, None, 2, 1, ctypes.byref(low)))
    finally:
        kernel32.CloseHandle(token)
    sid = ctypes.c_void_p()
    _check(advapi32.ConvertStringSidToSidW(LOW_INTEGRITY_SID, ctypes.byref(sid)))
    try:
        label = _SidAndAttributes(sid, 0x20)  # SE_GROUP_INTEGRITY
        size = ctypes.sizeof(label) + advapi32.GetLengthSid(sid)
        _check(advapi32.SetTokenInformation(low, 25, ctypes.byref(label), size))  # TokenIntegrityLevel
    except OSError:
        kernel32.CloseHandle(low)
        raise
    finally:
        kernel32.LocalFree(sid)
    return low


def _create_low_process(
    command_line: str, cwd: str, env: dict[str, str], stdin_handle: int, stdout_handle: int
) -> tuple[int, int]:
    advapi32, kernel32 = _libraries()
    low = _low_integrity_token()
    try:
        startup = _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        startup.dwFlags = _STARTF_USESTDHANDLES
        startup.hStdInput = stdin_handle
        startup.hStdOutput = stdout_handle
        startup.hStdError = stdout_handle
        info = _ProcessInformation()
        block = "".join(
            f"{key}={value}\0" for key, value in sorted(env.items(), key=lambda kv: kv[0].upper())
        )
        environment = ctypes.create_unicode_buffer(block + "\0")
        flags = _CREATE_UNICODE_ENVIRONMENT | _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW
        _check(
            advapi32.CreateProcessAsUserW(
                low,
                None,
                ctypes.create_unicode_buffer(command_line),
                None,
                None,
                True,
                flags,
                environment,
                cwd,
                ctypes.byref(startup),
                ctypes.byref(info),
            )
        )
        kernel32.CloseHandle(info.hThread)
        return int(info.dwProcessId), int(info.hProcess)
    finally:
        kernel32.CloseHandle(low)


def _exit_code(process_handle: int) -> int:
    _, kernel32 = _libraries()
    code = wintypes.DWORD()
    if not kernel32.GetExitCodeProcess(process_handle, ctypes.byref(code)):
        return 1
    return int(code.value)


def close_process_handle(process_handle: int) -> None:
    _, kernel32 = _libraries()
    with contextlib.suppress(OSError):
        kernel32.CloseHandle(process_handle)
