"""A relay between the copied application and the shared development database (D-608, D-610).

The user lets the copy of their application run directly on the development database (it has the data), on two
conditions: nothing is deleted there, and they see what was changed. There is no database user without the
DELETE right, so the database cannot enforce the first, and the application's own statements never pass through
a DebCraft tool. So the application is not given the database's address: it is given a port on this machine, and
this relay passes its PostgreSQL traffic on. On the way it

- refuses every statement that contains DELETE, TRUNCATE or DROP (the application gets an ordinary database
  error, the statement never reaches the server), and
- remembers every writing statement and the row counts the server reports, for the report to the user.

It reads only the frame of each message (type and length) and the text of Query and Parse messages; everything
else, including the password exchange, is passed on untouched. The application talks to the relay without TLS
(it is on localhost); the relay uses TLS to the server when the server offers it.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import ssl
import struct
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from forge.safety.sql_guard import split_statements

SSL_REQUEST = 80877103
GSS_REQUEST = 80877104
CANCEL_REQUEST = 80877102
BLOCKED_WORDS = ("delete", "truncate", "drop")
WRITE_WORDS = ("insert", "update", "merge", "alter", "create", "copy", "grant", "revoke", "call", "do")
_BLOCK_HINT = re.compile(r"delete|truncate|drop", re.IGNORECASE)
_FIRST_WORD = re.compile(r"^(?:\s|--[^\n]*\n|/\*.*?\*/)*([A-Za-z]+)", re.DOTALL)
_ROWS = re.compile(r"^(INSERT \d+|UPDATE|DELETE|MERGE|COPY) (\d+)$")
MAX_STATEMENT_TEXT = 300
MAX_STATEMENTS = 500  # distinct statements remembered; an application in a loop must not fill the memory
READ_CHUNK = 65536
BLOCKED_MESSAGE = (
    "DebCraft: {words} is not sent to the shared development database (the user's rule: nothing is deleted "
    "there). The statement was not run. Work on a copy of the table in the scratch schema instead, or tell the "
    "user which rows must go."
)


class DevProxyError(Exception):
    """The relay could not be started or could not reach the development database."""


@dataclass
class Sent:
    """One distinct writing statement of the application."""

    text: str
    kind: str  # its first word, upper case; "BLOCKED" statements keep their own first word
    blocked: bool
    times: int = 0
    reported: int = 0  # how many of `times` the user has already been told about


@dataclass
class Activity:
    statements: dict[str, Sent] = field(default_factory=dict)
    rows: dict[str, int] = field(default_factory=dict)  # "INSERT" -> rows the server reported
    rows_reported: dict[str, int] = field(default_factory=dict)
    dropped: int = 0  # statements not remembered because the list was full

    def note(self, text: str, kind: str, blocked: bool) -> None:
        short = " ".join(text.split())[:MAX_STATEMENT_TEXT]
        key = ("blocked:" if blocked else "") + short
        sent = self.statements.get(key)
        if sent is None:
            if len(self.statements) >= MAX_STATEMENTS:
                self.dropped += 1
                return
            sent = self.statements[key] = Sent(short, kind, blocked)
        sent.times += 1

    def summary(self, only_new: bool) -> str:
        """What the application wrote, as text for the user and the model. `only_new` reports what was not
        reported before and marks it as reported; an empty string when there is nothing to say."""
        passed: list[str] = []
        blocked: list[str] = []
        for sent in self.statements.values():
            count = sent.times - sent.reported if only_new else sent.times
            if count <= 0:
                continue
            line = f"- {sent.text}" + (f"  (x{count})" if count > 1 else "")
            (blocked if sent.blocked else passed).append(line)
            if only_new:
                sent.reported = sent.times
        rows = []
        for verb, total in sorted(self.rows.items()):
            count = total - self.rows_reported.get(verb, 0) if only_new else total
            if count > 0:
                rows.append(f"{count} row(s) by {verb}")
            if only_new:
                self.rows_reported[verb] = total
        if not passed and not blocked:
            return ""
        parts = []
        if passed:
            parts.append(
                "The application wrote to the shared Development database:\n"
                + "\n".join(passed)
                + (f"\nThe database reported: {', '.join(rows)}." if rows else "")
            )
        if blocked:
            parts.append(
                "Blocked by DebCraft, NOT sent to the Development database (nothing is deleted there):\n"
                + "\n".join(blocked)
            )
        if self.dropped:
            parts.append(f"({self.dropped} more statement(s) were not listed: the list is full.)")
        return "\n\n".join(parts)


def blocked_words(text: str) -> list[str]:
    """The removing words in the statement(s), outside strings and comments; empty when it may pass."""
    if not _BLOCK_HINT.search(text):
        return []
    found: set[str] = set()
    for statement in split_statements(text):
        found.update(word for word in statement.words if word in BLOCKED_WORDS)
    return sorted(found)


def write_kind(text: str) -> str:
    """The writing verb of a statement ("INSERT", "UPDATE", ...) or "" for one that only reads."""
    match = _FIRST_WORD.match(text)
    first = match.group(1).lower() if match else ""
    if first in WRITE_WORDS:
        return first.upper()
    if first == "with":  # a data-modifying WITH: the verb is somewhere inside
        words = [word for statement in split_statements(text) for word in statement.words]
        return next((word.upper() for word in words if word in ("insert", "update", "merge")), "")
    return ""


def _error(message: str) -> bytes:
    fields = b"SERROR\x00VERROR\x00C42501\x00M" + message.encode("utf-8") + b"\x00\x00"
    return b"E" + struct.pack("!I", len(fields) + 4) + fields


def _ready(status: bytes) -> bytes:
    return b"Z" + struct.pack("!I", 5) + status


def _text(payload: bytes, start: int = 0) -> tuple[str, int]:
    """A zero-terminated string of a message and the position after it."""
    end = payload.find(b"\x00", start)
    end = len(payload) if end == -1 else end
    return payload[start:end].decode("utf-8", "replace"), end + 1


class _Link:
    """One connection of the application, with the state the two directions share."""

    def __init__(self) -> None:
        self.status = b"I"  # the server's last transaction status: I idle, T in a transaction, E failed
        self.prepared: dict[str, str] = {}  # statement name -> its text, for counting at Bind
        self.skipping = False  # a Parse was refused: drop the rest of that batch up to its Sync
        self.refusal: bytes | None = None  # the error for the batch being skipped
        # asyncpg asks for the answer to a Parse with a Flush and sends no Sync until it has it: the error must be
        # sent at the Flush (when no earlier batch is still owed an answer), not held until a Sync that never comes.
        self.sent_early = False  # the error of the batch being skipped is already with the application
        self.flush_seen = False  # the application asked for an answer (Flush) and it is still waiting
        # Every Query and Sync passed on is answered by one ReadyForQuery, in order (the first one ends the
        # startup). Counting both tells which ReadyForQuery belongs to a refused batch, also when the
        # application sends several batches before it reads the answers.
        self.asked = 1
        self.answered = 0
        self.refusals: dict[int, bytes] = {}  # number of the ReadyForQuery -> the error to put before it


BENIGN_END = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, asyncio.IncompleteReadError)


class DevProxy:
    """`log(kind, **fields)` receives the facts of the relay (start, errors, stop) for the field log (D-615): a
    driver whose traffic the relay does not understand must leave a trace, not fail without a word."""

    def __init__(
        self,
        host: str,
        port: int,
        sslmode: str = "prefer",
        log: Callable[..., None] | None = None,
    ) -> None:
        self.host, self.port, self.sslmode = host, port, sslmode
        self.activity = Activity()
        self.local_port = 0
        self.connections = 0
        self.kinds: Counter[str] = Counter()  # message types the application sent: Q, P, B, E, S, ...
        self.errors: Counter[str] = Counter()  # what ended a connection other than the normal way
        self._log = log
        self._started = 0.0
        self._server: asyncio.Server | None = None
        self._links: set[asyncio.Task[None]] = set()

    def _note(self, kind: str, **fields: Any) -> None:
        if self._log is not None:
            self._log(kind, **fields)

    def _note_error(self, error: BaseException, where: str) -> None:
        """A connection ended in a way that is not the application closing it. Counted and written once per
        kind, with the first words of the message (these never hold a password: they are the library's text)."""
        if isinstance(error, (*BENIGN_END, asyncio.CancelledError)):
            return
        name = f"{where}:{type(error).__name__}"
        self.errors[name] += 1
        if self.errors[name] == 1:
            self._note("relay_error", where=where, type=type(error).__name__, text=str(error)[:120])

    async def start(self) -> int:
        try:  # fail now, with the reason, not at the application's first query
            _, probe = await asyncio.wait_for(self._open_upstream(), timeout=10)
        except (OSError, TimeoutError, ssl.SSLError, DevProxyError) as error:
            raise DevProxyError(f"The development database did not answer: {error}") from error
        probe.close()
        self._server = await asyncio.start_server(self._accept, "127.0.0.1", 0)
        self.local_port = int(self._server.sockets[0].getsockname()[1])
        self._started = time.monotonic()
        self._note("relay_start", local_port=self.local_port, sslmode=self.sslmode)
        return self.local_port

    async def close(self) -> None:
        was_running = self._server is not None
        if self._server is not None:
            self._server.close()
            self._server = None
        for task in list(self._links):
            task.cancel()
        for task in list(self._links):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if was_running:
            self._note("relay_stop", **self.stats())

    def stats(self) -> dict[str, Any]:
        """Numbers for the facts report: no statement text, no value."""
        statements = self.activity.statements.values()
        return {
            "seconds": round(time.monotonic() - self._started) if self._started else 0,
            "connections": self.connections,
            "messages": dict(self.kinds.most_common(12)),
            "writing_statements": sum(s.times for s in statements if not s.blocked),
            "refused_statements": sum(s.times for s in statements if s.blocked),
            "rows": dict(self.activity.rows),
            "errors": dict(self.errors.most_common(6)),
        }

    async def _open_upstream(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        if self.sslmode == "disable":
            return reader, writer
        writer.write(struct.pack("!II", 8, SSL_REQUEST))
        await writer.drain()
        answer = await reader.readexactly(1)
        if answer == b"S":
            verify = self.sslmode in ("verify-ca", "verify-full")
            context = ssl.create_default_context()
            if not verify:  # like libpq's prefer and require: encrypted, the certificate is not checked
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            await writer.start_tls(context, server_hostname=self.host if verify else None)
        elif self.sslmode in ("require", "verify-ca", "verify-full"):
            writer.close()
            raise DevProxyError("the server does not offer TLS, which the connection settings require")
        return reader, writer

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._links.add(task)
        upstream: asyncio.StreamWriter | None = None
        self.connections += 1
        try:
            upstream = await self._serve(reader, writer)
        except (OSError, asyncio.IncompleteReadError, ssl.SSLError, DevProxyError) as error:
            self._note_error(error, "connect")  # a normal close of either side is not counted
        finally:
            for end in (writer, upstream):
                if end is not None:
                    with contextlib.suppress(Exception):
                        end.close()
            if task is not None:
                self._links.discard(task)

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> asyncio.StreamWriter | None:
        while (
            True
        ):  # before the startup message a client may ask for TLS or GSS encryption: both are declined
            (length,) = struct.unpack("!I", await reader.readexactly(4))
            body = await reader.readexactly(length - 4)
            (code,) = struct.unpack("!I", body[:4])
            if code in (SSL_REQUEST, GSS_REQUEST):
                writer.write(b"N")
                await writer.drain()
                continue
            break
        server_reader, server_writer = await self._open_upstream()
        server_writer.write(struct.pack("!I", length) + body)
        await server_writer.drain()
        if code == CANCEL_REQUEST:  # a cancel is its own short connection
            return server_writer
        link = _Link()
        pumps = [
            asyncio.create_task(self._from_application(link, reader, writer, server_writer)),
            asyncio.create_task(self._from_server(link, server_reader, writer)),
        ]
        try:
            await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for pump in pumps:
                pump.cancel()
            for name, pump in zip(("application", "server"), pumps, strict=True):
                try:
                    await pump
                except asyncio.CancelledError:
                    pass
                except Exception as error:  # a bug or a message the relay does not understand: leave a trace
                    self._note_error(error, name)
        return server_writer

    async def _from_application(
        self,
        link: _Link,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        server: asyncio.StreamWriter,
    ) -> None:
        buffer = b""
        while True:
            chunk = await reader.read(READ_CHUNK)
            if not chunk:
                return
            buffer += chunk
            onward: list[bytes] = []
            back: list[bytes] = []
            while len(buffer) >= 5:
                (length,) = struct.unpack("!I", buffer[1:5])
                if len(buffer) < length + 1:
                    break
                message, buffer = buffer[: length + 1], buffer[length + 1 :]
                self._inspect(link, message, onward, back)
            if onward:
                server.write(b"".join(onward))
                await server.drain()
            if back:
                writer.write(b"".join(back))
                await writer.drain()

    def _inspect(self, link: _Link, message: bytes, onward: list[bytes], back: list[bytes]) -> None:
        """Decides what happens to one message of the application: passed on, dropped, or answered here."""
        kind, payload = message[:1], message[5:]
        self.kinds[kind.decode("ascii", "replace")] += 1
        if kind == b"Q":
            text, _ = _text(payload)
            words = blocked_words(text)
            if words:
                self.activity.note(text, write_kind(text) or words[0].upper(), blocked=True)
                refusal = BLOCKED_MESSAGE.format(words=" / ".join(word.upper() for word in words))
                back.append(_error(refusal) + _ready(b"I" if link.status == b"I" else b"E"))
                return
            verb = write_kind(text)
            if verb:
                self.activity.note(text, verb, blocked=False)
            link.asked += 1
        elif kind == b"P":
            name, position = _text(payload)
            text, _ = _text(payload, position)
            words = blocked_words(text)
            if words and not link.skipping:
                self.activity.note(text, write_kind(text) or words[0].upper(), blocked=True)
                link.skipping, link.sent_early, link.flush_seen = True, False, False
                link.refusal = _error(
                    BLOCKED_MESSAGE.format(words=" / ".join(word.upper() for word in words))
                )
                return
            link.prepared[name] = text
        elif kind == b"B" and not link.skipping:
            _, position = _text(payload)
            name, _ = _text(payload, position)
            text = link.prepared.get(name, "")
            verb = write_kind(text) if text else ""
            if verb:
                self.activity.note(text, verb, blocked=False)
        elif kind == b"H" and link.skipping and link.refusal is not None and not link.sent_early:
            if link.asked - link.answered == 0:
                back.append(link.refusal)  # nothing earlier is owed: the error goes now
                link.sent_early = True
            else:
                link.flush_seen = True  # it goes when the last earlier answer has been passed on
        elif kind == b"S":
            link.asked += 1
            if link.skipping and link.refusal is not None and not link.sent_early:
                # The Sync goes on: the server's ReadyForQuery ends the batch for the client, after the error.
                link.refusals[link.asked] = link.refusal
            link.skipping, link.refusal, link.sent_early, link.flush_seen = False, None, False, False
        elif kind == b"F":
            link.asked += 1  # a function call is answered by a ReadyForQuery too
        elif kind == b"X":
            link.skipping = False
        if link.skipping:
            return  # the rest of a refused batch (Bind, Describe, Execute) never reaches the server
        onward.append(message)

    async def _from_server(
        self, link: _Link, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        buffer = b""
        while True:
            chunk = await reader.read(READ_CHUNK)
            if not chunk:
                return
            buffer += chunk
            out: list[bytes] = []
            while len(buffer) >= 5:
                (length,) = struct.unpack("!I", buffer[1:5])
                if len(buffer) < length + 1:
                    break
                message, buffer = buffer[: length + 1], buffer[length + 1 :]
                kind = message[:1]
                if kind == b"C":
                    tag, _ = _text(message[5:])
                    match = _ROWS.match(tag)
                    if match:
                        verb = match.group(1).split()[0]
                        self.activity.rows[verb] = self.activity.rows.get(verb, 0) + int(match.group(2))
                elif kind == b"Z":
                    link.status = message[5:6]
                    link.answered += 1
                    refusal = link.refusals.pop(link.answered, None)
                    if refusal is not None:
                        # The answer to the Sync of a refused batch: the client is told about the refusal, and a
                        # transaction that was open counts as failed, so the application rolls it back.
                        out.append(refusal)
                        if link.status == b"T":
                            message = _ready(b"E")
                out.append(message)
                if (
                    kind == b"Z"
                    and link.flush_seen
                    and link.refusal is not None
                    and not link.sent_early
                    and link.asked - link.answered == 0
                ):
                    out.append(link.refusal)  # the application is waiting for it (see _Link.flush_seen)
                    link.sent_early, link.flush_seen = True, False
            if out:
                writer.write(b"".join(out))
                await writer.drain()
