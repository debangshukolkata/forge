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
        result = await sign_in(login, visible=args.visible)
        if not result.ok:
            hand_off = (
                " Call app_login again with visible=true so a window opens, and ask the user to sign in there "
                "(if gcloud or the company login has expired, they run `gcloud auth login` first)."
                if result.needs_user
                else ""
            )
            return ToolResult(ok=False, content=f"Not signed in to {login.name}: {result.message}{hand_off}")
        seconds = TokenStore().put(login.token_name, result.token)
        return ToolResult(
            ok=True,
            content=f"Signed in to {login.name}. The token is kept as {login.token_name} (valid for about "
            f"{seconds // 60} minutes) and is not shown. Call {login.host} with http_request and "
            f'token_env="{login.token_name}"; it signs in again by itself when the token ends.',
        )
