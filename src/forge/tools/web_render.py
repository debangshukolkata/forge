"""Reading a page that builds itself with JavaScript, through a headless browser (D-209).

Read-only and isolated: a fresh profile with no cookies or sign-ins, downloads off, images/media/fonts not
loaded, a time limit, and every request the page makes (not only the first) goes through the same address
guard as web_fetch. It is the expensive fallback: web_fetch uses it only when the plain fetch came back empty
or thin. Anything that stops it (Playwright or a browser missing) is reported as 'unavailable', never as a
crash."""

from __future__ import annotations

import contextlib
from typing import Any

from forge.tools.web_guard import LOCAL_SCHEMES, WebPolicy, check_resolving

RENDER_TIMEOUT_S = 25
SETTLE_MS = 4000  # how long to wait for the page's own requests to quiet down after it has loaded
BLOCKED_RESOURCES = frozenset({"image", "media", "font"})


class RenderUnavailable(Exception):
    """The headless browser cannot be used on this machine (the reason is in the message)."""


async def render_html(url: str, policy: WebPolicy, timeout_s: float = RENDER_TIMEOUT_S) -> tuple[str, str]:
    """(page HTML after its scripts ran, final URL)."""
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise RenderUnavailable("playwright is not installed (pip install playwright)") from error

    async with async_playwright() as playwright:
        browser = await _launch(playwright)
        try:
            context = await browser.new_context(
                accept_downloads=False,
                service_workers="block",
                locale="en-US",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Forge/1.0",
            )
            verdicts: dict[str, str | None] = {}

            async def guard(route: Any) -> None:
                request = route.request
                if request.resource_type in BLOCKED_RESOURCES:
                    await route.abort()
                    return
                if request.url.split(":", 1)[0] not in LOCAL_SCHEMES:
                    host = request.url.split("/")[2] if "//" in request.url else request.url
                    if host not in verdicts:
                        verdicts[host] = await check_resolving(request.url, policy)
                    if verdicts[host] is not None:
                        await route.abort()
                        return
                await route.continue_()

            await context.route("**/*", guard)
            page = await context.new_page()
            page.set_default_timeout(timeout_s * 1000)
            try:
                response = await page.goto(url, wait_until="domcontentloaded")
                if response is not None and response.status >= 400:  # an error page is not the page
                    raise RenderUnavailable(f"the site answered HTTP {response.status}")
                with contextlib.suppress(PlaywrightError):
                    await page.wait_for_load_state("networkidle", timeout=SETTLE_MS)
                return await page.content(), page.url
            except PlaywrightError as error:
                raise RenderUnavailable(
                    f"the browser could not load it: {str(error).splitlines()[0][:160]}"
                ) from error
        finally:
            await browser.close()


async def _launch(playwright: Any) -> Any:
    reasons = []
    for options in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return await playwright.chromium.launch(headless=True, **options)
        except Exception as error:  # no such browser here: try the next one
            reasons.append(str(error).splitlines()[0][:100])
    raise RenderUnavailable("no Edge, Chrome or Chromium could be started: " + "; ".join(reasons[:2]))
