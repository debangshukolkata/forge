"""The HTTP API of AgentHub PG (same surface as AgentHub)."""

from __future__ import annotations

import hashlib
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agenthub_pg import store
from agenthub_pg.agent import ContextOverflow, run
from agenthub_pg.settings import RUN_LOG, settings


def token_is_valid(header: str | None) -> bool:
    if not header or not header.startswith("Bearer "):
        return False
    digest = hashlib.sha256(header.removeprefix("Bearer ").strip().encode()).hexdigest()
    return digest == settings.console_token_sha256


def log_run(entry: dict[str, object]) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}) + "\n")


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict[str, object]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorised(self) -> bool:
        if token_is_valid(self.headers.get("Authorization")):
            return True
        self._send(401, {"error": "a console token is required: Authorization: Bearer <token>"})
        return False

    def do_GET(self) -> None:
        if not self._authorised():
            return
        if self.path == "/api/agents":
            self._send(200, {"agents": store.agent_names()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._authorised():
            return
        parts = self.path.strip("/").split("/")
        if len(parts) != 4 or parts[:2] != ["api", "agents"] or parts[3] not in ("run", "stream"):
            self._send(404, {"error": "not found"})
            return
        agent = store.load_agent(parts[2])
        if agent is None:
            self._send(404, {"error": f"no agent named {parts[2]}"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            question = str(json.loads(self.rfile.read(length) or b"{}")["question"])
        except (ValueError, KeyError):
            self._send(422, {"error": 'send {"question": "..."}'})
            return
        if parts[3] == "stream":
            self._stream(agent, question)
            return
        try:
            result = run(agent, question)
            store.record_run(agent.name, "ok")
        except ContextOverflow as error:
            log_run(
                {
                    "agent": agent.name,
                    "question": question,
                    "status": "failed",
                    "tool": error.tool,
                    "tool_result_chars": error.size,
                    "limit": error.limit,
                }
            )
            self._send(200, {"status": "failed", "error": "the agent could not finish"})
            return
        except Exception as error:  # the reason goes to the run log only
            log_run(
                {
                    "agent": agent.name,
                    "question": question,
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}"[:500],
                }
            )
            self._send(200, {"status": "failed", "error": "the agent could not finish"})
            return
        log_run(
            {
                "agent": agent.name,
                "question": question,
                "status": "ok",
                "tools": result.tools,
                "tool_result_chars": result.tool_result_chars,
            }
        )
        self._send(200, {"status": "ok", "tool": (result.tools or [""])[-1], "answer": result.answer})

    def _stream(self, agent: store.Agent, question: str) -> None:
        """The same run as `run`, but every step is sent as a server-sent event when it happens."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def send(event: dict[str, object]) -> None:
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()

        send({"type": "run_started", "agent": agent.name})
        try:
            result = run(agent, question, on_event=send)
            store.record_run(agent.name, "ok")
        except ContextOverflow as error:
            log_run(
                {
                    "agent": agent.name,
                    "question": question,
                    "status": "failed",
                    "tool": error.tool,
                    "tool_result_chars": error.size,
                    "limit": error.limit,
                }
            )
            send({"type": "error", "message": "the agent could not finish"})
            return
        except Exception as error:  # the reason goes to the run log only
            log_run(
                {
                    "agent": agent.name,
                    "question": question,
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}"[:500],
                }
            )
            send({"type": "error", "message": "the agent could not finish"})
            return
        log_run(
            {
                "agent": agent.name,
                "question": question,
                "status": "ok",
                "tools": result.tools,
                "tool_result_chars": result.tool_result_chars,
            }
        )
        send({"type": "final", "answer": result.answer})

    def log_message(self, format: str, *args: object) -> None:  # quiet: runs go to the run log
        return


def main() -> None:
    store.ensure_seeded()
    server = ThreadingHTTPServer(("127.0.0.1", settings.port), Handler)
    print(f"AgentHub PG listening on http://127.0.0.1:{settings.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
