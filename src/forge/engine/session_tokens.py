"""At the start of a session: is there a valid token for each environment the user marked `warn_without_token`? (D-603)

For each such environment DebCraft looks at the stored token (its own expiry and, when the user gave a check address,
the server's answer). A token that is not valid is replaced by a sign-in without a window, but only for an environment
that was signed in before: a window is never opened by itself. When there is still no valid token the user gets a
warning in the chat and the model gets the fact pinned, so it says so plainly instead of calling an environment it
cannot reach. Names and times only: no token value is read into a message."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge.config import forge_home
from forge.errors import ConfigError
from forge.protocol.events import EventType
from forge.toolkit.app_logins import EnvLogin, load_logins
from forge.tools.app_login import MARKER, TokenStatus, profile_dir, renew, token_status

if TYPE_CHECKING:
    from forge.engine.session_host import SessionHost

PIN_SLOT = "tokens"


def _line(login: EnvLogin, status: TokenStatus) -> str:
    if status.usable:
        left = f", about {status.minutes} minutes left" if status.minutes is not None else ""
        note = f" ({status.detail})" if status.detail else ""
        return f"- {login.token_name} ({login.name}): valid{left}{note}."
    reason = {
        "missing": "not signed in yet",
        "ended": "ended",
        "rejected": status.detail or "the server refused it",
    }.get(status.state, status.state)
    return (
        f"- {login.token_name} ({login.name}): NO VALID TOKEN ({reason}). Calls to {login.host} will fail. Tell the user "
        "plainly at once; app_login signs in (visible=true opens the window; `gcloud auth login` first if Google asks)."
    )


async def check_tokens(host: SessionHost) -> None:
    """Looks at the marked environments, signs in silently where it may, warns where there is still no valid token."""
    try:
        logins = [login for login in load_logins().values() if login.warn_without_token]
    except ConfigError as error:
        await host.bus.publish(
            EventType.NOTICE, {"kind": "token_warning", "text": f"app_logins.yaml: {error}"}
        )
        return
    if not logins:
        return
    lines: list[str] = []
    warnings: list[str] = []
    for login in logins:
        status = await token_status(login)
        signed_in_before = (profile_dir(login, forge_home()) / MARKER).exists()
        if not status.usable and signed_in_before and (await renew(login)).ok:
            status = await token_status(login)
        lines.append(_line(login, status))
        if not status.usable:
            warnings.append(
                f"No valid {login.token_name} for {login.name}. DebCraft cannot call {login.host} until you sign in: "
                "ask it to sign in to that environment, and run `gcloud auth login` first if Google asks."
            )
    host.context_manager.pinned.set(PIN_SLOT, "\n".join(lines))
    for text in warnings:
        await host.bus.publish(EventType.NOTICE, {"kind": "token_warning", "text": text})
