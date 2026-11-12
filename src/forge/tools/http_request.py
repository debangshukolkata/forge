"""`http_request`: calls the API of the application running on this machine (D-568).

Used for a smoke test, and to run the application the way its users do: call an agent's endpoint, read what
came back and how large each part of it is. Two things make that possible without breaking the rule that
secrets never reach the model:

- A token the user obtained elsewhere (for example from the application's frontend) sits in DebCraft's own
  .env file under a name the user chose. The model names the variable; DebCraft puts the value into the request
  header. Only names the user listed can be used, so the model cannot send DebCraft's own keys anywhere.
- The answer is reported with its size and, for JSON, the size of each part, and the whole body is kept in a
  file: an answer too large for an agent's context is then visible as exactly that.
"""

from __future__ import annotations

import json
from typing import Any, Literal

import httpx
from pydantic import Field

from forge.config import forge_home, load_secrets
from forge.llm.tokens import count_text_tokens
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.browser import local_url
from forge.tools.interaction import OptionSpec

HTTP_TIMEOUT_S = 30
MAX_TIMEOUT_S = 900
TOKEN_NAMES_ENV = "FORGE_REQUEST_TOKEN_NAMES"  # in DebCraft's .env: more names, separated by commas
DEFAULT_TOKEN_NAMES = ("DEVELOPMENT_INSTANCE_TOKEN",)
SHAPE_DEPTH = 3
SHAPE_LINES = 40
NOT_SET = "is not set in"
ADDED = "I have added it"
NO_TOKEN = "I cannot get a token"
SHOWN_HEADERS = ("content-type", "location", "allow", "www-authenticate", "retry-after")


def allowed_token_names(listed: str | None) -> set[str]:
    return {*DEFAULT_TOKEN_NAMES, *(name.strip() for name in (listed or "").split(",") if name.strip())}


def _size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), default=str))


def json_shape(value: Any, name: str = "body", depth: int = 0) -> list[str]:
    """What a JSON answer consists of and how large each part is: the part that is too big stands out."""
    pad = "  " * depth
    if isinstance(value, dict):
        lines = [f"{pad}{name}: object with {len(value)} keys, {_size(value):,} characters"]
        if depth < SHAPE_DEPTH:
            for key, item in sorted(value.items(), key=lambda pair: -_size(pair[1]))[:12]:
                lines += json_shape(item, str(key), depth + 1)
        return lines
    if isinstance(value, list):
        lines = [f"{pad}{name}: list of {len(value)} items, {_size(value):,} characters"]
        if value and depth < SHAPE_DEPTH:
            lines += json_shape(value[0], "each item (the first)", depth + 1)
        return lines
    text = json.dumps(value, default=str)
    shown = text if len(text) <= 60 else text[:57] + "..."
    return [
        f"{pad}{name}: {type(value).__name__} {shown}"
        + (f" ({len(text):,} characters)" if len(text) > 60 else "")
    ]


class HttpRequest(Tool):
    name = "http_request"
    description = (
        "Call the API of the application running on this machine: method, URL on localhost, optional JSON body "
        "and headers. Use it to check an endpoint and to run the application as its users do (for example to "
        "call an agent and see what it answers). The result shows the status, the size of the answer in "
        "characters and tokens, for JSON the size of each part, and then the body (a long one is cut and kept "
        "whole in a file you can read in ranges). When the endpoint needs a token that only the user can get: "
        "`token_env` = the NAME of the variable in DebCraft's .env file that holds it (the user puts it there; "
        "DEVELOPMENT_INSTANCE_TOKEN unless they said otherwise). DebCraft sends it as `Authorization: Bearer "
        "<token>` (change `token_header` and `token_prefix` if the API expects something else); you never see "
        "the value and never write one into a header yourself. `timeout_s`: raise it for a call that runs an "
        "agent (up to 900)."
    )

    class Args(ToolArgs):
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
        url: str
        json_body: Any = Field(default=None, alias="json")
        headers: dict[str, str] = Field(default_factory=dict)
        token_env: str = ""
        token_header: str = "Authorization"
        token_prefix: str = "Bearer "
        timeout_s: int = Field(default=HTTP_TIMEOUT_S, ge=1, le=MAX_TIMEOUT_S)

    def summary(self, args: HttpRequest.Args) -> str:
        return f"{args.method} {args.url}" + (f" (token from {args.token_env})" if args.token_env else "")

    async def run(self, args: HttpRequest.Args, context: ToolContext) -> ToolResult:
        problem = local_url(args.url)
        if problem:
            return ToolResult(
                ok=False,
                content=f"Not sent: {problem.replace('browser tools only open', 'http_request only calls')}.",
            )
        headers = dict(args.headers)
        token = ""
        if args.token_env:
            name = args.token_env.strip()
            token, refusal = self._token(name)
            if refusal and NOT_SET in refusal and context.ask_user is not None:
                # Only the user can get this token: ask them now instead of leaving it to the model to remember
                # (in three live runs it was told to ask and went on without the API instead).
                answer = await context.ask_user(
                    f"The application's API needs a token that only you can get. Please add it to DebCraft's .env file as {name}.",
                    f"Open {load_secrets(forge_home()).source or 'the DebCraft .env file'} and add the line\n\n"
                    f"    {name}=<the token>\n\n"
                    "Get the token the way you normally do for this application (for example from its login page "
                    "or console). Do not paste it into the chat. A token that expires can be replaced in the same "
                    "line later.",
                    [
                        OptionSpec(label=ADDED, description="The line is in the file; call the API now."),
                        OptionSpec(label=NO_TOKEN, description="DebCraft goes on without calling the API."),
                    ],
                    ADDED,
                )
                if answer.startswith(f"The user chose: {ADDED}"):
                    token, refusal = self._token(name)
                else:
                    refusal = (
                        f"The user cannot provide {name} ({answer}). The API cannot be called, so the requirement "
                        "cannot be proven through it here: check what you can another way and say plainly in your "
                        "report that the run through the API was not verified."
                    )
            if refusal:
                return ToolResult(ok=False, content=refusal)
            headers[args.token_header] = f"{args.token_prefix}{token}"
        try:
            async with httpx.AsyncClient(timeout=args.timeout_s) as client:
                response = await client.request(args.method, args.url, json=args.json_body, headers=headers)
        except httpx.TimeoutException:
            return ToolResult(
                ok=False,
                content=f"No answer within {args.timeout_s} s. If the call runs an agent, raise `timeout_s`; "
                "look at the application's output (read_background) for what it was doing.",
            )
        except httpx.HTTPError as error:
            return ToolResult(
                ok=False, content=f"Request failed: {type(error).__name__}: {error}. Is the app running?"
            )
        body = response.text
        if token:
            body = body.replace(token, "[token hidden]")  # an API that echoes the header must not show it
        shape: list[str] = []
        try:
            parsed = response.json()
            shape = json_shape(parsed)[:SHAPE_LINES]
            body = json.dumps(parsed, indent=1)
            if token:
                body = body.replace(token, "[token hidden]")
        except ValueError:
            pass
        shown, full_path = (
            context.cap_output(body, "tool") if context.workspace is not None else (body[:6000], None)
        )
        interesting = {k: v for k, v in response.headers.items() if k.lower() in SHOWN_HEADERS}
        lines = [
            f"HTTP {response.status_code}",
            str(interesting),
            f"Answer: {len(response.text):,} characters, about {count_text_tokens(response.text):,} tokens.",
        ]
        if shape:
            lines += ["Parts by size:", *shape]
        if response.status_code in (401, 403):
            lines.append(
                f"Not authorised. The token in {args.token_env} may have expired or be for another instance: ask the "
                "user for a fresh one (ask_user), then call again."
                if args.token_env
                else "Not authorised. If the endpoint needs a token only the user can get, ask them to put it in "
                "DebCraft's .env file as DEVELOPMENT_INSTANCE_TOKEN: call again with "
                "`token_env`."
            )
        return ToolResult(
            ok=response.status_code < 500,
            content="\n".join(lines) + "\n\n" + shown,
            meta={"status": response.status_code, "characters": len(response.text)},
            full_output_path=full_path,
        )

    @staticmethod
    def _token(name: str) -> tuple[str, str]:
        """(the token, '') or ('', why it cannot be used). The .env is read at call time: a token expires and
        the user replaces it while the session is open; reading registers the value for masking everywhere."""
        secrets = load_secrets(forge_home())
        where = secrets.source or "DebCraft's .env file"
        if name not in allowed_token_names(secrets.get(TOKEN_NAMES_ENV)):
            return "", (
                f"{name} is not a token the user has released for requests. Usable: "
                f"{', '.join(sorted(allowed_token_names(secrets.get(TOKEN_NAMES_ENV))))}. The user can release "
                f"another name by listing it in {TOKEN_NAMES_ENV} in {where}."
            )
        value = secrets.get(name)
        if not value:
            return "", (
                f"{name} {NOT_SET} {where}. Ask the user (ask_user) to add the line `{name}=<the token>` to "
                "that file, saying where they get the token; then call again. Do not ask them to paste the "
                "token into the chat."
            )
        return value, ""
