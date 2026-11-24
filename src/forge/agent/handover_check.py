"""What the final reply must be honest about (D-644, the video agent run of 2026-11-24).

There the model handed over a curl it had never run, with a token of a signing key it had invented, after checks on
`FAKE_MP4` bytes; the user found out when the curl failed. These checks read the reply and what the session did, and
give the model one note each. They are notes, never refusals."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from forge.toolkit.base import ToolContext

CURL = re.compile(r"\bcurl(?:\.exe)?\b(?:[^\n]*\\\r?\n|[^\n]*`\r?\n|[^\n]*\^\r?\n)*[^\n]*", re.IGNORECASE)
URL = re.compile(r"https?://[^\s'\"`)>\]]+")
METHOD = re.compile(r"(?:-X|--request)[ =]?['\"]?([A-Za-z]+)")
BODY = re.compile(r"(?:^|\s)(?:-d|--data[\w-]*|--json|-F|--form)\b")
PLACEHOLDER = re.compile(r"^(?:<.*>|\{.*\}|\$.*|:\w+|\d+|[0-9a-fA-F-]{32,36})$")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def curls_in(reply: str) -> list[tuple[str, str]]:
    """(method, url without query) of every curl in the reply."""
    found: dict[tuple[str, str], None] = {}
    for text in CURL.findall(reply):
        url = URL.search(text)
        if url is None:
            continue
        method = METHOD.search(text)
        name = method.group(1).upper() if method else ("POST" if BODY.search(text) else "GET")
        found[(name, url.group(0).split("?", 1)[0].rstrip("/,;."))] = None
    return list(found)


def _same_call(method: str, url: str, key: str) -> bool:
    """The same method, host and path; a number or a placeholder in the path stands for any value."""
    other_method, _, other_url = key.partition(" ")
    if other_method.upper() != method:
        return False
    a, b = urlparse(url), urlparse(other_url)
    if a.port != b.port:
        return False
    hosts = {a.hostname or "", b.hostname or ""}
    if len(hosts) > 1 and not hosts <= LOCAL_HOSTS:
        return False
    left, right = a.path.strip("/").split("/"), b.path.strip("/").split("/")
    return len(left) == len(right) and all(
        x == y or (PLACEHOLDER.match(x) is not None and PLACEHOLDER.match(y) is not None)
        for x, y in zip(left, right, strict=True)
    )


def curl_note(context: ToolContext, reply: str) -> str:
    """For a curl that was not run, or whose last run failed."""
    open_calls = []
    for method, url in curls_in(reply):
        matching = [key for key in context.api_calls if _same_call(method, url, key)]
        if any(key not in context.api_failed for key in matching):
            continue
        why = f"its last run failed: {context.api_failed[matching[0]]}" if matching else "you never ran it"
        open_calls.append(f"{method} {url} ({why})")
    fresh = [call for call in open_calls if call not in context.handover_told]
    if not fresh:
        return ""
    context.handover_told.update(fresh)
    return (
        "You gave the user a curl that is not proven: "
        + "; ".join(fresh[:4])
        + ". For an address on this machine: "
        "make exactly this call with http_request now, with real data, and fix what fails. For another host: make it "
        "only when it changes nothing there. Then tell the user, next to the curl: whether you ran exactly this call "
        "and what it answered, and which token it needs and where that token comes from (a token of the local "
        "application and one of the dev environment are not the same: follow in the code where the caller's token is "
        "passed on, and say when one token cannot serve both). If you cannot run it, say 'not run' and why."
    )


def failed_calls_note(context: ToolContext, turn_start_step: int) -> str:
    """Calls of this turn to the local application whose last answer is a failure, after the code was changed."""
    if context.last_code_edit_step <= turn_start_step:
        return ""
    failing = [
        f"{key} ({context.api_failed[key]})"
        for key, step in context.api_calls.items()
        if step > turn_start_step
        and key in context.api_failed
        and (urlparse(key.partition(" ")[2]).hostname or "") in LOCAL_HOSTS
    ]
    fresh = [call for call in failing if call not in context.handover_told]
    if not fresh:
        return ""
    context.handover_told.update(fresh)
    return (
        "These calls to the application still end in a failure: "
        + "; ".join(fresh[:5])
        + ". Find the cause (the "
        "application's own output, read_background) and make each one work, or, when the failure is the expected "
        "answer of a negative test, say so in one line. A 401, 403 or 422 about a token or a signature means the "
        "user's call will fail the same way: say it now, with the cause."
    )


def made_up_note(context: ToolContext, reply: str) -> str:
    """For made-up settings or data the reply does not name."""
    lowered = reply.lower()
    fresh = [
        item
        for item in sorted(context.made_up)
        if item not in context.handover_told and item.split(" ", 1)[1].lower() not in lowered
    ]
    if not fresh:
        return ""
    context.handover_told.update(fresh)
    return (
        "The application was run with made-up values: "
        + "; ".join(fresh[:10])
        + ". Name them in your reply and say "
        "what they stand for and which of your checks depend on them: those checks do not show that it works with the "
        "real values, so do not call them verified. Say what the user has to expect with the real ones (for example, "
        "a token of the real environment is refused when the signing key is invented)."
    )
