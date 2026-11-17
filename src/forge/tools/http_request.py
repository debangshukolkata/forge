"""`http_request`: calls the API of the application running on this machine (D-568), and any other http(s)
address the task needs, without a question (D-621); a token goes only to this machine and to named hosts.

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

import asyncio
import json
import re
import time
import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote, urlparse

import httpx
from pydantic import Field

from forge.config import env_file_path, forge_home, load_secrets
from forge.errors import ConfigError
from forge.llm.tokens import count_text_tokens
from forge.safety.redact import default_redactor
from forge.toolkit.app_keys import (
    TOKEN_NAMES_ENV,
    allowed_token_names,
    remember_auth,
    remembered_auth,
    user_value,
)
from forge.toolkit.app_logins import (
    LOGINS_FILE,
    EnvLogin,
    TokenStore,
    default_login,
    login_for_host,
    login_for_token,
)
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.app_login import ensure_token
from forge.tools.browser import LOCAL_HOSTS
from forge.tools.interaction import OptionSpec
from forge.tools.kept_secrets import blank, check_names, keep_from_answer
from forge.tools.stream_summary import summarize_stream
from forge.workspace.run_notes import RunNotes

HTTP_TIMEOUT_S = 30
MAX_TIMEOUT_S = 900
SHAPE_DEPTH = 3
SHAPE_LINES = 40
NOT_SET = "is not set in"
ADDED = "I have added it"
NO_TOKEN = "I cannot get a token"
SHOWN_HEADERS = ("content-type", "location", "allow", "www-authenticate", "retry-after")


__all__ = ["TOKEN_NAMES_ENV", "HttpRequest", "allowed_token_names", "json_shape"]


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


NoneType = type(None)


def _place_token(args: HttpRequest.Args, token: str, headers: dict[str, str], body: Any) -> tuple[str, Any]:
    """(url, json body) with the token under `token_field` where `token_in` says; a cookie goes into the headers."""
    field = args.token_field.strip()
    if args.token_in == "query":
        separator = "&" if "?" in args.url else "?"
        return f"{args.url}{separator}{quote(field)}={quote(token, safe='')}", body
    if args.token_in == "cookie":
        headers["Cookie"] = "; ".join(filter(None, [headers.get("Cookie", ""), f"{field}={token}"]))
        return args.url, body
    return args.url, {**(body or {}), field: token}


MAX_STREAM_LINES = 50_000
STREAM_SHOWN_CHARS = 1200


async def _read_stream(
    client: httpx.AsyncClient,
    args: HttpRequest.Args,
    url: str,
    body: Any,
    headers: dict[str, str],
) -> tuple[httpx.Response, list[tuple[float, str]], bool]:
    """Sends the request and reads the answer line by line with the second each line arrived, until the stream ends,
    `timeout_s` passes (what arrived is kept) or an absurd number of lines is reached. The answer is rebuilt as a
    response, so the rest of the tool treats it like any other."""
    started = time.perf_counter()
    items: list[tuple[float, str]] = []
    status = 0
    response_headers: dict[str, str] = {}
    cut = False
    try:
        async with asyncio.timeout(args.timeout_s):
            async with client.stream(args.method, url, json=body, headers=headers) as response:
                status, response_headers = response.status_code, dict(response.headers)
                async for line in response.aiter_lines():
                    items.append((time.perf_counter() - started, line))
                    if len(items) >= MAX_STREAM_LINES:
                        cut = True
                        break
    except TimeoutError as error:
        if not status:
            raise httpx.ReadTimeout("no answer before the time limit") from error
        cut = True
    text = "\n".join(line for _, line in items)
    response_headers.pop("content-encoding", None)  # the text below is already decoded
    response_headers.pop("content-length", None)
    return httpx.Response(status, headers=response_headers, content=text.encode("utf-8")), items, cut


def _keep_stream(context: ToolContext, body: str) -> tuple[str, str | None]:
    """The whole stream goes to a file the model can read in ranges; the call's result shows only its beginning."""
    if context.workspace is None:
        return body[:STREAM_SHOWN_CHARS], None
    folder = context.workspace.jail.check(context.workspace.forge_dir / "tool_outputs")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}-stream.txt"
    path.write_text(body, encoding="utf-8")
    relative = path.relative_to(context.workspace.root).as_posix()
    head = body[:STREAM_SHOWN_CHARS]
    more = f" (first {len(head):,} of {len(body):,} characters)" if len(body) > len(head) else ""
    return (
        f"{head}\n\n[The whole stream{more} is in {relative}; read it in ranges with read_file offset/limit.]",
        str(path),
    )


def _token_may_go_to(host: str) -> tuple[bool, str]:
    """(yes or no, what is wrong with the file). A token is sent only to this machine and to a host the user named
    in app_logins.yaml. http_request may call any address (the user, 2026-11-16, D-621), so this is what keeps a
    token of the user from being sent to an address the model chose (invariant 3)."""
    if host in LOCAL_HOSTS:
        return True, ""
    try:
        return login_for_host(host) is not None, ""
    except ConfigError as error:
        return False, str(error)


class HttpRequest(Tool):
    name = "http_request"
    description = (
        "Call an HTTP API: the application running on this machine, its development or test instance, or any "
        "other address the task needs: method, URL, optional JSON body and headers. No approval is asked for a "
        "call. A token is sent only to this machine and to the hosts the user named in app_logins.yaml. "
        "Use it to check an endpoint and to run the application as its users do (for example to "
        "call an agent and see what it answers). The result shows the status, the size of the answer in "
        "characters and tokens, for JSON the size of each part, and then the body (a long one is cut and kept "
        "whole in a file you can read in ranges). The token of the user's application is the one DebCraft signs "
        "in for: call the endpoint without a token; when it answers 401 or 403, DebCraft signs in to the "
        "environment of that host in app_logins.yaml (for this machine: the environment `dev`) and repeats the "
        "call with its token. You pass nothing and never ask the user for a token. `token_env` is only for "
        "another token: the token name of a named environment, or a NAME the user released in "
        "FORGE_REQUEST_TOKEN_NAMES whose value is in DebCraft's .env file. It is sent as `Authorization: Bearer "
        "<token>` (change `token_header` and `token_prefix` if the API expects something else); you never see "
        "the value and never write one into a header yourself. The tool adapts by itself, so never ask the user "
        "to change a line in the file: a value saved as `Bearer <token>` is sent correctly; when the API "
        "refuses the token with `Bearer`, the same call is tried with the bare token. The file is "
        "read on every call: a token the user has just saved is used at once, without a restart. `timeout_s`: "
        "raise it for a call that runs an agent (up to 900). `stream`: true for an API that streams its answer "
        "(server-sent events or one JSON object per line): the call is read to its end and the result is an "
        "account by event (the kinds, the tool events in order with their sizes, errors, the longest silence, "
        "the final answer), with the whole stream kept in a file you can read in ranges. `keep_secret`: when the "
        "answer holds a secret that a command needs (a value the secret store or a key service does not give "
        "out on this machine but the development instance does), map the variable NAME to the path of the "
        'field in the JSON answer, for example {"ARGOCD_TOKEN": "secret.secretValue"}: the value is taken out '
        "of the answer before you see it and set for the commands of this session after the user agreed. Never "
        "read such a value from the answer and write it into a command, a file or the code yourself."
    )

    class Args(ToolArgs):
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
        url: str
        json_body: Any = Field(default=None, alias="json")
        headers: dict[str, str] = Field(default_factory=dict)
        token_env: str = ""
        token_header: str = "Authorization"
        token_prefix: str = "Bearer "
        # Where the token goes when the API does not read a header (RS13): the name of the query parameter, cookie
        # or JSON body field is `token_field`. The value is put there by the tool; the model never sees it.
        token_in: Literal["header", "query", "cookie", "body"] = "header"
        token_field: str = ""
        # An API that streams its answer (server-sent events or one JSON object per line): the call is read to its
        # end (or `timeout_s`) and returned as an account by event instead of one block of text (RS9, D-599).
        stream: bool = False
        # A secret the answer holds goes to the project's commands under a name and is never shown (D-611):
        # {"ARGOCD_TOKEN": "secret.secretValue"} = variable name -> dotted path of the field in the JSON answer.
        keep_secret: dict[str, str] = Field(default_factory=dict)
        timeout_s: int = Field(default=HTTP_TIMEOUT_S, ge=1, le=MAX_TIMEOUT_S)

    def summary(self, args: HttpRequest.Args) -> str:
        return f"{args.method} {args.url}" + (f" (token from {args.token_env})" if args.token_env else "")

    async def run(self, args: HttpRequest.Args, context: ToolContext) -> ToolResult:
        refusal = self._host_refusal(args.url)
        if refusal:
            return ToolResult(ok=False, content=f"Not sent: {refusal}.")
        if args.keep_secret:
            problem = check_names(args.keep_secret) or (
                "`keep_secret` reads one JSON answer: leave out `stream`" if args.stream else ""
            )
            if problem:
                return ToolResult(ok=False, content=f"Not sent: {problem}.")
        headers = dict(args.headers)
        sent_url, sent_json = args.url, args.json_body
        token = ""
        name = args.token_env.strip()
        login_env = login_for_token(name) if name else None
        host = (urlparse(args.url).hostname or "").lower()
        token_host, file_problem = _token_may_go_to(host)
        if name and not token_host:
            where = forge_home() / LOGINS_FILE
            return ToolResult(
                ok=False,
                content=(
                    f"Not sent: {file_problem} The file is {where}. No token can go to {host or args.url} until "
                    "it is repaired: tell the user, and offer to fix the file (settings_file)."
                    if file_problem
                    else f"Not sent: a token goes only to this machine and to the hosts the user named in {where}; "
                    f"{host or args.url} is neither. Call it without `token_env`, or, when it is an instance of "
                    "the user's application, offer to add it to that file (settings_file)."
                ),
            )
        if login_env is not None:
            if host not in LOCAL_HOSTS and host != login_env.host:
                return ToolResult(
                    ok=False,
                    content=f"Not sent: {name} is the token of {login_env.host}, not of {host or args.url}.",
                )
            # a valid token, or one DebCraft gets by itself, or (after the gcloud card) with the user's help (D-603)
            ensured = await ensure_token(login_env, ask=context.ask_user)
            if not ensured.token:
                return ToolResult(
                    ok=False,
                    content=f"{name} is not available: {ensured.message} Tell the user plainly that there is no "
                    f"valid {name}.",
                )
        if name:
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
            if args.token_in == "header":
                headers[args.token_header] = f"{args.token_prefix}{token}"
            elif not args.token_field.strip():
                return ToolResult(
                    ok=False,
                    content=f'token_in="{args.token_in}" needs `token_field`: the name it goes under.',
                )
            elif args.token_in == "body" and not isinstance(sent_json, dict | NoneType):
                return ToolResult(
                    ok=False, content='token_in="body" needs `json` to be an object (or empty).'
                )
            else:
                sent_url, sent_json = _place_token(args, token, headers, sent_json)
        # What to try when the API refuses the call (401, 403: nothing was done, so sending again is safe). The
        # user was asked to rewrite the token line and to restart for things the tool can find out itself (D-570).
        # Each try: the headers, what to tell the model when it is the one that works, and (name, header, prefix).
        origin = "/".join(args.url.split("/")[:3])
        workspace = context.workspace
        tries: list[tuple[dict[str, str], str, tuple[str, str, str]]] = []
        own_login: EnvLogin | None = None
        if token and args.token_in != "header":
            tries.append(
                (headers, "", ("", "", ""))
            )  # no scheme to adapt: the API takes it where the model said
        elif token:
            tries.append((headers, "", (name, args.token_header, args.token_prefix)))
            if args.token_prefix and login_env is None:  # a token DebCraft signed in for is always a bearer
                tries.append(
                    (
                        {**headers, args.token_header: token},
                        f"This API takes the token without `{args.token_prefix.strip()}`: with it the call was "
                        'refused, with the bare token it was accepted. Pass token_prefix="" from now on; the '
                        "user has nothing to change in the file.",
                        (name, args.token_header, ""),
                    )
                )
        elif not name and token_host and not any(key.lower() == "authorization" for key in headers):
            known = remembered_auth(workspace).get(origin) if workspace is not None else None
            if known:  # how this API took the token before: used at once, the model need not remember it
                token, _ = self._token(known["token_env"])
                if token:
                    tries.append(
                        (
                            {**headers, known["header"]: f"{known['prefix']}{token}"},
                            f"Sent with {known['token_env']} the way this API accepted it before.",
                            (known["token_env"], known["header"], known["prefix"]),
                        )
                    )
            else:
                tries.append((headers, "", ("", "", "")))
        if not tries:
            tries.append((headers, "", ("", "", "")))
        # The token of the application is the one DebCraft signs in for (the user, 2026-11-16, D-626): when the
        # call is refused, the environment of this host signs in and the call is repeated, below. Also when the
        # model wrote an Authorization header itself: it never holds a real token, and live it sent
        # `Bearer dummy-token` and went on without the API.
        own_header = any(key.lower() == "authorization" for key in args.headers)
        clean = {key: value for key, value in headers.items() if key.lower() != "authorization"}
        wrote = "The Authorization header you wrote was refused and left out: never write a token yourself. "
        if not name and token_host:
            own_login = default_login(host, local=host in LOCAL_HOSTS)
        adapted = ""
        signed_in_as = sign_in_problem = ""
        streamed: list[tuple[float, str]] | None = None
        cut = False
        try:
            # A call to this machine never goes through the company proxy: httpx reads the Windows proxy settings,
            # and Zscaler answered a call to http://127.0.0.1:5062 with its "blocked, invalid server IP" page on the
            # office laptop (D-632), so the model wrote "localhost is blocked by policy" into its memory.
            async with httpx.AsyncClient(timeout=args.timeout_s, trust_env=host not in LOCAL_HOSTS) as client:

                async def send(with_headers: dict[str, str]) -> httpx.Response:
                    nonlocal streamed, cut
                    if args.stream:
                        answer, streamed, cut = await _read_stream(
                            client, args, sent_url, sent_json, with_headers
                        )
                        return answer
                    return await client.request(args.method, sent_url, json=sent_json, headers=with_headers)

                for try_headers, note, form in tries:
                    response = await send(try_headers)
                    if response.status_code not in (401, 403):
                        adapted = note
                        if form[0] and workspace is not None:
                            remember_auth(workspace, origin, *form)
                        break
                if login_env is not None and response.status_code in (401, 403) and args.token_in == "header":
                    fresh = await ensure_token(login_env, ask=context.ask_user, force=True)
                    if fresh.token:  # the server refused the token: get another once and repeat the call
                        token = fresh.token
                        retry = {**headers, args.token_header: f"{args.token_prefix}{token}"}
                        response = await client.request(args.method, sent_url, json=sent_json, headers=retry)
                        adapted = f"The token of {login_env.name} had ended: DebCraft signed in again and repeated the call."
                if own_login is not None and response.status_code in (401, 403):
                    # Signing in may open a window, so it happens only after the endpoint asked for a token.
                    signed_in_as = own_login.name
                    for force in (False, True):
                        ensured = await ensure_token(own_login, ask=context.ask_user, force=force)
                        if not ensured.token:
                            sign_in_problem = ensured.message
                            break
                        token = ensured.token
                        response = await send({**clean, "Authorization": f"Bearer {token}"})
                        if response.status_code not in (401, 403):
                            adapted = (
                                (wrote if own_header else "")
                                + f"The endpoint asked for a token, so DebCraft signed in to {own_login.name} and sent "
                                f"{own_login.token_name} itself. Nothing to pass and nothing to ask the user."
                            )
                            if workspace is not None:
                                remember_auth(
                                    workspace, origin, own_login.token_name, "Authorization", "Bearer "
                                )
                            break
        except httpx.TimeoutException:
            return ToolResult(
                ok=False,
                content=f"No answer within {args.timeout_s} s. If the call runs an agent, raise `timeout_s`; "
                "look at the application's output (read_background) for what it was doing.",
            )
        except httpx.HTTPError as error:
            return ToolResult(
                ok=False,
                content=f"Request failed: {type(error).__name__}: {str(error).replace(token, '[token hidden]') if token else error}. Is the app running?",
            )
        context.api_calls[f"{args.method} {args.url.split('?', 1)[0]}"] = context.step
        if response.status_code < 400 and context.workspace is not None:
            # The call that worked is written down by the tool: a later session repeats it instead of searching again (D-597).
            notes = RunNotes(context.workspace)
            notes.record_call(
                args.method, args.url, args.json_body, name, response.status_code, stream=args.stream
            )
            if context.pin is not None:
                context.pin("run_notes", notes.render())
        body = response.text
        if token:
            body = body.replace(token, "[token hidden]")  # an API that echoes the header must not show it
        shape: list[str] = []
        kept_lines: list[str] = []
        hidden: list[tuple[str, str]] = []
        try:
            parsed = response.json()
            if args.keep_secret and response.status_code < 400:
                kept_lines, hidden = await keep_from_answer(
                    args.keep_secret, parsed, urlparse(args.url).hostname or args.url, context
                )
                parsed = json.loads(blank(json.dumps(parsed), hidden))
            if token:  # an API that echoes what it received must not show the token in the summary either
                parsed = json.loads(json.dumps(parsed).replace(token, "[token hidden]"))
            shape = json_shape(parsed)[:SHAPE_LINES]
            body = json.dumps(parsed, indent=1)
            if token:
                body = body.replace(token, "[token hidden]")
        except ValueError:
            if args.keep_secret:
                kept_lines = ["Nothing was kept: the answer is not JSON."]
        body = blank(body, hidden)
        if args.keep_secret and not kept_lines:
            kept_lines = [f"Nothing was kept: the call answered HTTP {response.status_code}."]
        if streamed is not None:
            if token:
                streamed = [(at, line.replace(token, "[token hidden]")) for at, line in streamed]
            shown, full_path = _keep_stream(context, body)
        else:
            shown, full_path = (
                context.cap_output(body, "tool") if context.workspace is not None else (body[:6000], None)
            )
        interesting = {k: v for k, v in response.headers.items() if k.lower() in SHOWN_HEADERS}
        lines = [
            f"HTTP {response.status_code}",
            str(interesting),
            f"Answer: {len(response.text):,} characters, about {count_text_tokens(response.text):,} tokens.",
        ]
        if streamed is not None:
            total = streamed[-1][0] if streamed else 0.0
            lines += summarize_stream(streamed, total, cut)
        if shape:
            lines += ["Parts by size:", *shape]
        if adapted:
            lines.insert(1, adapted)
        lines[1:1] = kept_lines
        if response.status_code in (401, 403):
            signed = signed_in_as or (login_env.name if login_env is not None else "")
            released = sorted(allowed_token_names(load_secrets(forge_home()).get(TOKEN_NAMES_ENV)))
            unsigned = not name and not signed and token_host and len(released) == 1
            if unsigned:
                # The one fixed token the user released is for this: the tool takes the step itself (and asks
                # the user for a missing line), because the model was told to and went on without the API.
                kept = {key: value for key, value in args.headers.items() if key.lower() != "authorization"}
                again = await self.run(
                    args.model_copy(update={"token_env": released[0], "headers": kept}), context
                )
                note = (
                    (wrote if own_header else "")
                    + f"The endpoint needs a token; DebCraft used {released[0]}, the one the user released, "
                    "itself."
                )
                return again.model_copy(update={"content": f"{note}\n{again.content}"})
            lines.append(
                f"Not authorised. DebCraft could not sign in to {signed}: {sign_in_problem} Tell the user "
                "plainly; do not ask them for a token."
                if sign_in_problem
                else f"Not authorised. DebCraft signed in to {signed} and its token was refused: the account may "
                "have no right to this endpoint, or the endpoint belongs to another environment. Tell the user "
                "plainly; do not ask them for a token."
                if signed
                else f"Not authorised. The token in {name} was sent with and without `Bearer` and refused both "
                "times: it may have expired or be for another instance. Ask the user to replace the line in "
                f"{env_file_path(forge_home())} with a fresh token (ask_user; do not ask for the value, a "
                "restart or a change of its form), then call again."
                if name
                else f"Not authorised. The user released a token for requests: call again with `token_env` = "
                f"{' or '.join(released)}."
                if released
                else f"Not authorised, and no environment in {forge_home() / LOGINS_FILE} covers "
                f"{host or args.url}, so DebCraft has no token for it. If this is the user's application, add "
                "its environment with settings_file (ask the user only for the address of its login page): "
                "DebCraft then signs in by itself. Do not ask the user for a token."
            )
        return ToolResult(
            ok=response.status_code < 500,
            content="\n".join(lines) + "\n\n" + shown,
            meta={"status": response.status_code, "characters": len(response.text)},
            full_output_path=full_path,
        )

    @staticmethod
    def _host_refusal(url: str) -> str:
        """ "" when the call may go out: any http(s) address, without a question (the user, 2026-11-16, D-621).
        What is limited is where a token goes (`_token_may_go_to`), not where a call goes."""
        return "" if urlparse(url).scheme in ("http", "https") else "only http(s) URLs"

    @staticmethod
    def _token(name: str) -> tuple[str, str]:
        """(the token, '') or ('', why it cannot be used). The .env is read at call time: a token expires and
        the user replaces it while the session is open; reading registers the value for masking everywhere."""
        if login_for_token(name) is not None:  # a token DebCraft signed in for itself (D-603)
            stored = TokenStore().get(name)
            return (
                (stored, "")
                if stored
                else ("", f"{name} is not signed in: call app_login for its environment.")
            )
        secrets = load_secrets(forge_home())
        where = secrets.source or "DebCraft's .env file"
        if name not in allowed_token_names(secrets.get(TOKEN_NAMES_ENV)):
            return "", (
                f"{name} is not a token the user has released for requests. For the user's application "
                "leave `token_env` out: DebCraft signs in by itself when the endpoint asks for a token. "
                "Released names: "
                f"{', '.join(sorted(allowed_token_names(secrets.get(TOKEN_NAMES_ENV)))) or 'none'}. The user "
                f"can release another name by listing it in {TOKEN_NAMES_ENV} in {where}."
            )
        value = user_value(name)  # app.env first, then DebCraft's .env
        if not value:
            return "", (
                f"{name} {NOT_SET} {where}. Ask the user (ask_user) to add the line `{name}=<the token>` to "
                "that file, saying where they get the token; then call again. Do not ask them to paste the "
                "token into the chat."
            )
        default_redactor.register(value, name)  # also a released name without TOKEN or KEY in it
        # The user may save the header value as they copied it ("Bearer eyJ..."): the scheme is the tool's job.
        bare = re.sub(r"(?i)^bearer\s+", "", value.strip())
        default_redactor.register(bare, name)
        return bare, ""
