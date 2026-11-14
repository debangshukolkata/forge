"""The copy's own settings that point at the shared development database are held back (DV10, D-613).

The user's local codebase is set up to use the development database: its env file holds that address and a
login that may write. The copy DebCraft works on inherits the file, so starting the copy would connect it
straight to the shared database: no red card, no relay, nothing that stops a delete (D-608, D-610). The user
chose that DebCraft blocks this until the application is deliberately pointed somewhere:

- `dev_settings` reads the env files of the copy and finds the settings that hold the development database's
  address (a URL with its host, port and database; or separate host, port and database settings);
- `Refuser` is a listener on this machine that answers every PostgreSQL connection with an error saying what
  to call instead;
- the session gives every command those settings with the refuser's address in place of the server's. An
  environment variable wins over the same name in an env file for the usual loaders (python-dotenv,
  pydantic-settings, dotenv for Node), so the copy cannot reach the development database by accident.

`use_scratch_database` and `use_dev_database` replace the held-back values for the settings they are given.
Values of the env files are read here and never leave this module: callers get names and the replacement.
"""

from __future__ import annotations

import asyncio
import contextlib
import struct
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import dotenv_values

from forge.db.dev_proxy import GSS_REQUEST, SSL_REQUEST

LOCAL_NAMES = {"localhost", "127.0.0.1", "::1"}
NOT_SETTINGS = (".example", ".sample", ".template", ".dist")
MAX_ENV_FILE_BYTES = 200_000
REFUSAL = (
    "DebCraft: the settings {names} of this copy point at the shared development database, so the connection "
    "was not made. Point the application at a database on purpose, then start it again: copy the rows it needs "
    "with db_copy_table and call use_scratch_database with these settings (no approval needed), or call "
    "use_dev_database with them (the user approves on a red card). Do not change the application or its env "
    "file to get around this."
)


@dataclass
class HeldBack:
    """What was found: per setting its kind and, for a URL, the original value (to keep scheme, login and
    database when the address is replaced). `files` are the env files it was found in, for the user."""

    kinds: dict[str, str] = field(default_factory=dict)  # name -> "url" | "host" | "port"
    urls: dict[str, str] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)

    def values(self, port: int) -> dict[str, str]:
        """The settings with the refuser's address in place of the development database's."""
        result: dict[str, str] = {}
        for name, kind in self.kinds.items():
            if kind == "host":
                result[name] = "127.0.0.1"
            elif kind == "port":
                result[name] = str(port)
            else:
                parsed = urlsplit(self.urls[name])
                login = parsed.netloc.rpartition("@")[0]
                query = urlencode(
                    [(k, v) for k, v in parse_qsl(parsed.query) if k != "sslmode"] + [("sslmode", "disable")]
                )
                netloc = f"{login + '@' if login else ''}127.0.0.1:{port}"
                result[name] = urlunsplit(parsed._replace(netloc=netloc, query=query))
        return result


def _same_host(one: str, other: str) -> bool:
    one, other = one.strip().lower(), other.strip().lower()
    return one == other or (one in LOCAL_NAMES and other in LOCAL_NAMES)


def env_files(folders: list[Path]) -> list[Path]:
    """The env files at the top of the copy and of the application's folder (not examples or templates)."""
    found: dict[Path, None] = {}
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            name = path.name.lower()
            if not path.is_file() or name.endswith(NOT_SETTINGS):
                continue
            if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
                with contextlib.suppress(OSError):
                    if path.stat().st_size <= MAX_ENV_FILE_BYTES:
                        found[path.resolve()] = None
    return list(found)


def dev_settings(folders: list[Path], dev_url: str) -> HeldBack:
    """The settings in the copy's env files that hold the development database's address."""
    target = urlsplit(dev_url)
    host, port, database = target.hostname or "", str(target.port or 5432), target.path.lstrip("/")
    held = HeldBack()
    if not host:
        return held
    for path in env_files(folders):
        try:
            values = {name: value for name, value in dotenv_values(path).items() if value}
        except (OSError, ValueError):
            continue
        before = len(held.kinds)
        hosts, ports, databases = [], [], []
        for name, value in values.items():
            if "://" in value:
                try:
                    parsed = urlsplit(value.strip())
                    same = (
                        _same_host(parsed.hostname or "", host)
                        and str(parsed.port or 5432) == port
                        and parsed.path.lstrip("/") == database
                    )
                except ValueError:
                    continue
                if same:
                    held.kinds[name], held.urls[name] = "url", value.strip()
                continue
            upper = name.upper()
            if "HOST" in upper and _same_host(value, host):
                hosts.append(name)
            elif "PORT" in upper and value.strip() == port:
                ports.append(name)
            elif value.strip() == database:
                databases.append(name)
        # Separate settings count only when the file names all three: a host called localhost alone says nothing.
        if hosts and ports and databases:
            held.kinds.update(dict.fromkeys(hosts, "host"))
            held.kinds.update(dict.fromkeys(ports, "port"))
        if len(held.kinds) > before:
            held.files.append(path.name)
    return held


def _fatal(message: str) -> bytes:
    fields = b"SFATAL\x00VFATAL\x00C42501\x00M" + message.encode("utf-8") + b"\x00\x00"
    return b"E" + struct.pack("!I", len(fields) + 4) + fields


class Refuser:
    """Answers every PostgreSQL connection on its port with an error that says what to do instead."""

    def __init__(self, names: list[str]) -> None:
        self.message = REFUSAL.format(names=", ".join(names))
        self.local_port = 0
        self.refused = 0
        self._server: asyncio.Server | None = None

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._answer, "127.0.0.1", 0)
        self.local_port = int(self._server.sockets[0].getsockname()[1])
        return self.local_port

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None

    async def _answer(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while (
                True
            ):  # a client may first ask for TLS or GSS encryption: declined, then it sends its startup
                (length,) = struct.unpack("!I", await asyncio.wait_for(reader.readexactly(4), timeout=10))
                body = await asyncio.wait_for(reader.readexactly(max(0, min(length - 4, 10_000))), timeout=10)
                if len(body) >= 4 and struct.unpack("!I", body[:4])[0] in (SSL_REQUEST, GSS_REQUEST):
                    writer.write(b"N")
                    await writer.drain()
                    continue
                break
            self.refused += 1
            writer.write(_fatal(self.message))
            await writer.drain()
        except (OSError, asyncio.IncompleteReadError, TimeoutError, struct.error):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()
