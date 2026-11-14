"""`app_login`: DebCraft signs in to an environment of a web application itself and keeps the token (D-603).

It does what the user does by hand: opens the login page of the environment, clicks the buttons the user described in
`app_logins.yaml`, waits for the page that follows, and reads the token from the cookie or the request header named
there. The browser profile is private to DebCraft (`<DebCraft Home>/browser_profile/<environment>`): the first time it
opens a visible window, so the user can pass a Google or company login (DebCraft never types credentials and never
passes MFA); afterwards it signs in without a window until the session ends. The token goes to the private token store
(`toolkit/app_logins.py`) and is never in the result, an event or the chat."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import Field

from forge.config import forge_home
from forge.errors import ConfigError
from forge.toolkit import field_log
from forge.toolkit.app_logins import EnvLogin, TokenStore, load_logins
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

CHANNELS = ("msedge", "chrome", None)  # None = Playwright's bundled Chromium
MARKER = ".debcraft_signed_in"
STEP_SECONDS_HEADLESS = 20
STEP_SECONDS_VISIBLE = 240  # time for a person to pass a Google or company login in the open window
HEADER_WAIT_SECONDS = 10


@dataclass
class SignIn:
    ok: bool
    token: str = ""
    message: str = ""
    needs_user: bool = False  # a window should be opened for the user to sign in first


def profile_dir(login: EnvLogin, home: Path) -> Path:
    return home / "browser_profile" / login.name


async def _click(page: Any, text: str, timeout_ms: int) -> None:
    target = page.get_by_role("button", name=text, exact=True).or_(page.get_by_text(text, exact=True))
    await target.first.click(timeout=timeout_ms)


async def sign_in(login: EnvLogin, home: Path | None = None, visible: bool = False) -> SignIn:
    """Runs the steps of the environment in the private browser profile and returns the token it found."""
    home = home or forge_home()
    profile = profile_dir(login, home)
    first_time = not (profile / MARKER).exists()
    show = visible or first_time
    seconds = STEP_SECONDS_VISIBLE if show else STEP_SECONDS_HEADLESS
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return SignIn(
            False,
            message="Playwright is not installed here, so DebCraft cannot open a browser (forge doctor).",
        )
    profile.mkdir(parents=True, exist_ok=True)
    playwright = await async_playwright().start()
    context: Any = None
    errors: list[str] = []
    try:
        for channel in CHANNELS:
            try:
                context = await playwright.chromium.launch_persistent_context(
                    str(profile), channel=channel, headless=not show
                )
                break
            except Exception as error:
                errors.append(f"{channel or 'chromium'}: {str(error).splitlines()[0]}")
        if context is None:
            return SignIn(False, message="No browser could be started (" + "; ".join(errors) + ").")
        page = context.pages[0] if context.pages else await context.new_page()
        header_token: dict[str, str] = {}

        def watch(request: Any) -> None:
            value = request.headers.get(login.token_header or "-", "")
            if value and urlparse(request.url).hostname == login.host:
                header_token["value"] = value.removeprefix("Bearer ").strip()

        if login.token_header:
            page.on("request", watch)
        await page.goto(login.login_url, wait_until="domcontentloaded", timeout=seconds * 1000)
        for number, step in enumerate(login.steps, 1):
            try:
                if step.action == "click":
                    await _click(page, step.value, seconds * 1000)
                elif step.action == "wait_url":
                    await page.wait_for_url(
                        lambda url, wanted=step.value: wanted in url, timeout=seconds * 1000
                    )
                else:
                    await page.wait_for_timeout(step.seconds * 1000)
            except Exception as error:
                where = urlparse(page.url).hostname or "?"
                note = (
                    f" The browser is at {where}, not at {login.host}: a Google or company sign-in may be waiting."
                    if where != login.host
                    else ""
                )
                return SignIn(
                    False,
                    message=f"Step {number} ({step.action} {step.value!r}) did not complete in {seconds} s: "
                    f"{str(error).splitlines()[0]}.{note}",
                    needs_user=not show,
                )
        token = ""
        if login.token_cookie:
            cookies = await context.cookies([login.login_url])
            token = next((c["value"] for c in cookies if c["name"] == login.token_cookie), "")
        else:
            deadline = time.monotonic() + HEADER_WAIT_SECONDS
            while not header_token and time.monotonic() < deadline:
                await page.wait_for_timeout(500)
            token = header_token.get("value", "")
        if not token:
            where = (
                f"the cookie {login.token_cookie}"
                if login.token_cookie
                else f"the {login.token_header} header"
            )
            return SignIn(
                False, message=f"The steps finished but {where} was not found: check app_logins.yaml."
            )
        (profile / MARKER).write_text("signed in", encoding="utf-8")
        return SignIn(True, token=token)
    finally:
        if context is not None:
            await context.close()
        await playwright.stop()


async def renew(login: EnvLogin, home: Path | None = None) -> SignIn:
    """Signs in again without a window (a token ended, or the API answered 401) and keeps the new token."""
    result = await sign_in(login, home, visible=False)
    if result.ok:
        TokenStore(home).put(login.token_name, result.token)
    return result


@dataclass
class TokenStatus:
    state: str  # valid | ended | missing | rejected | unchecked
    minutes: int | None = None  # how long the token still lasts by its own expiry
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.state in (
            "valid",
            "unchecked",
        )  # unchecked: the check could not be made (network), the token is not known to be bad


async def probe(login: EnvLogin, token: str) -> tuple[bool | None, str]:
    """True when the environment's check address accepts the token, False when it refuses it (401 or 403), None when
    it could not be asked (the host does not resolve, a time-out): then nothing is known against the token."""
    import httpx

    cookies = {login.token_cookie: token} if login.token_cookie else None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                login.check_url, headers={"Authorization": f"Bearer {token}"}, cookies=cookies
            )
    except httpx.HTTPError as error:
        return None, f"{type(error).__name__}: {str(error)[:120]}"
    if response.status_code in (401, 403):
        return False, f"HTTP {response.status_code}"
    return response.status_code < 400, f"HTTP {response.status_code}"


async def token_status(login: EnvLogin, home: Path | None = None, check: bool = True) -> TokenStatus:
    """Whether the stored token of this environment can be used: not past its expiry and, when the user gave a check
    address, accepted by the server."""
    store = TokenStore(home)
    token = store.get(login.token_name)
    if token is None:
        return TokenStatus("ended" if store.remaining(login.token_name) is not None else "missing")
    minutes = (store.remaining(login.token_name) or 0) // 60
    if check and login.check_url:
        ok, detail = await probe(login, token)
        if ok is False:
            return TokenStatus("rejected", minutes, f"the server refused it ({detail})")
        if ok is None:
            return TokenStatus("unchecked", minutes, f"could not be checked: {detail}")
    return TokenStatus("valid", minutes)


@dataclass
class Ensured:
    token: str  # "" when no token could be got
    message: str = ""


async def ensure_token(
    login: EnvLogin, home: Path | None = None, ask: Any = None, force: bool = False
) -> Ensured:
    """A usable token for the environment, by the order the user described (D-603): the stored one when it is valid
    (its expiry and the check address); else sign in again without a window; and when that fails, ask the user on a
    card to run `gcloud auth login` and try again (a window opens if the site needs the person). `force`: the server
    just refused the token, so the stored one is not trusted."""
    started = time.monotonic()
    store = TokenStore(home)

    def noted(path: str, ensured: Ensured, detail: str = "") -> Ensured:
        """The way the token was got goes to the field log (D-615): the facts that close TK5 are which path was
        taken, how long it took and how long the token lasts. Numbers and names, never the token."""
        span = store.lifetime(login.token_name)
        field_log.write(
            "sign_in",
            home,
            env=login.name,
            token_name=login.token_name,
            path=path,
            ok=bool(ensured.token),
            seconds=round(time.monotonic() - started, 1),
            minutes_left=(store.remaining(login.token_name) or 0) // 60,
            lifetime_min=span[0] // 60 if span else None,
            exp_claim=span[1] if span else None,
            detail=detail or ensured.message,
        )
        return ensured

    if force:
        store.forget(login.token_name)
    else:
        status = await token_status(login, home)
        if status.usable:
            return noted("stored", Ensured(store.get(login.token_name) or ""), status.detail)
        if status.state == "rejected":
            store.forget(login.token_name)
    result = await renew(login, home)
    if result.ok:
        return noted("silent" if not force else "silent_after_refusal", Ensured(result.token))
    # No token without a window: open one, so the user can sign in there (the browser profile of DebCraft is not the
    # user's own Edge, so Google may ask once; the first run is visible already).
    silent_problem = result.message
    result = await sign_in(login, home, visible=True)
    if result.ok:
        TokenStore(home).put(login.token_name, result.token)
        return noted("window", Ensured(result.token), f"silent sign-in failed first: {silent_problem}")
    if ask is None:
        return noted("failed", Ensured("", result.message))
    from forge.tools.interaction import OptionSpec

    answer = await ask(
        f"DebCraft could not get the {login.name} token, even after opening the sign-in window.",
        f"{result.message}\n\n"
        "If Google asked for a login, run `gcloud auth login` in PowerShell and sign in the window "
        "DebCraft opens. If you are sure you are signed in, there may be another issue (the site, the steps in "
        "app_logins.yaml). Choose Done once you have signed in: DebCraft opens the window again and tries once more.",
        [
            OptionSpec(label="Done", description="I signed in; try again."),
            OptionSpec(label="Skip", description="Do not sign in now."),
        ],
        "Done",
    )
    if not answer.startswith("The user chose: Done"):
        return noted(
            "skipped", Ensured("", f"Not signed in to {login.name}: the user skipped it ({answer[:80]}).")
        )
    result = await sign_in(login, home, visible=True)
    if result.ok:
        TokenStore(home).put(login.token_name, result.token)
    return noted("card_done", Ensured(result.token, "" if result.ok else result.message))


class AppTokenStatus(Tool):
    name = "app_token_status"
    sends_outside = True
    description = (
        "Check, without signing in, whether the kept token of an environment (dev, SIT) is still valid: its own expiry "
        "and, when app_logins.yaml gives a check address, a call to that address with the token. Use it before a run "
        "against the environment; if the token is not valid, call app_login. The token is never shown."
    )

    class Args(ToolArgs):
        environment: str

    def summary(self, args: AppTokenStatus.Args) -> str:
        return f"check the {args.environment} token"

    async def run(self, args: AppTokenStatus.Args, context: ToolContext) -> ToolResult:
        try:
            login = load_logins().get(args.environment)
        except ConfigError as error:
            return ToolResult(ok=False, content=str(error))
        if login is None:
            return ToolResult(
                ok=False, content=f"There is no environment {args.environment!r} in app_logins.yaml."
            )
        status = await token_status(login)
        if status.usable:
            left = f" (about {status.minutes} minutes left)" if status.minutes is not None else ""
            return ToolResult(
                ok=True,
                content=f"{login.token_name} for {login.name} is valid{left}. {status.detail}".strip(),
            )
        return ToolResult(
            ok=False,
            content=f"No valid {login.token_name} for {login.name}: {status.state}. {status.detail} "
            "Call app_login for this environment (the user may need to run `gcloud auth login`).",
        )


class AppLogin(Tool):
    name = "app_login"
    sends_outside = True
    description = (
        "Sign in to an environment of the web application (dev, SIT) the way the user does, in a browser DebCraft keeps "
        "for itself, and keep the token. `environment` is one of the environments the user described in "
        "app_logins.yaml. The token is stored under its name (for example DEV_TOKEN) and is never shown to you: "
        "call the environment's API with http_request and token_env set to that name. The first time a window opens "
        "for the user to pass the Google or company login; say so and wait for them. If gcloud or a company login is "
        "needed, the user does it: you cannot type credentials or pass MFA. `visible`: true to open the window again "
        "(the session ended, or the sign-in needs the person)."
    )

    class Args(ToolArgs):
        environment: str
        visible: bool = Field(default=False)

    def summary(self, args: AppLogin.Args) -> str:
        return f"sign in to {args.environment}"

    async def run(self, args: AppLogin.Args, context: ToolContext) -> ToolResult:
        try:
            logins = load_logins()
        except ConfigError as error:
            return ToolResult(ok=False, content=str(error))
        login = logins.get(args.environment)
        if login is None:
            known = ", ".join(sorted(logins)) or "none: the user has not described any yet (app_logins.yaml)"
            return ToolResult(
                ok=False, content=f"There is no environment {args.environment!r}. Known: {known}."
            )
        if args.visible:  # the user asked for the window: no check, no gcloud card
            result = await sign_in(login, visible=True)
            if result.ok:
                TokenStore().put(login.token_name, result.token)
            ensured = Ensured(result.token, "" if result.ok else result.message)
        else:
            ensured = await ensure_token(login, ask=context.ask_user)
        if not ensured.token:
            return ToolResult(
                ok=False,
                content=f"Not signed in to {login.name}: {ensured.message} Tell the user plainly that there is no "
                f"valid {login.token_name}, so calls to {login.host} cannot be made until they sign in "
                "(app_login with visible=true opens the window; `gcloud auth login` first if Google asks).",
            )
        minutes = (TokenStore().remaining(login.token_name) or 0) // 60
        return ToolResult(
            ok=True,
            content=f"Signed in to {login.name}. The token is kept as {login.token_name} (valid for about "
            f"{minutes} minutes) and is not shown. Call {login.host} with http_request and "
            f'token_env="{login.token_name}"; it checks the token and signs in again by itself when it ends.',
        )
