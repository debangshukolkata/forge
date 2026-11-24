"""The HTTP API."""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from recqa import recordings


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, body: object) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict[str, object]:
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

    def do_GET(self) -> None:
        found = re.fullmatch(r"/recordings/(\d+)", self.path)
        if not found:
            self.send_json(404, {"error": "not found"})
            return
        try:
            moments = recordings.load(found.group(1))
        except FileNotFoundError:
            self.send_json(404, {"error": "no such recording"})
            return
        self.send_json(
            200, {"id": found.group(1), "moments": len(moments), "seconds": moments[-1].seconds}
        )

    def do_POST(self) -> None:
        self.send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    port = int(os.environ.get("RECQA_PORT", "8790"))
    print(f"RecQA listening on http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
