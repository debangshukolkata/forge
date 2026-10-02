"""Browser tools (spec §9.7) with Playwright: v1 use is checking the app Forge built — its API and Swagger UI
— so pages are limited to the local machine (localhost/127.0.0.1); other sites are read with web_fetch.
Launch order: Edge -> Chrome -> Playwright's bundled Chromium. One headless browser per session, started on
first use; console messages and network requests are recorded for browser_console/browser_network.
http_request calls the local app's API directly (smoke tests)."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
CHANNELS = ("msedge", "chrome", None)  # None = Playwright's bundled Chromium
MAX_LOG = 200
SNAPSHOT_CHARS = 12_000
HTTP_TIMEOUT_S = 30


def local_url(url: str) -> str | None:
    """None when allowed; else why not."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "only http(s) URLs"
    if (parsed.hostname or "").lower() not in LOCAL_HOSTS:
        return f"the browser tools only open the local app (localhost); use web_fetch for {parsed.hostname}"
    return None


class BrowserSession:
    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self.page: Any = None
        self.channel: str | None = None
        self.console: list[str] = []
        self.network: list[str] = []

    async def ensure(self) -> Any:
        if self.page is not None:
            return self.page
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        errors = []
        for channel in CHANNELS:
            try:
                self._browser = await self._playwright.chromium.launch(channel=channel, headless=True)
                self.channel = channel or "chromium"
                break
            except Exception as error:
                errors.append(f"{channel or 'chromium'}: {str(error).splitlines()[0]}")
        if self._browser is None:
            await self._playwright.stop()
            self._playwright = None
            raise RuntimeError("No browser could be started (" + "; ".join(errors) + ")")
        self.page = await self._browser.new_page()
        self.page.on("console", lambda m: self._log(self.console, f"[{m.type}] {m.text}"))
        self.page.on("pageerror", lambda e: self._log(self.console, f"[pageerror] {e}"))
        self.page.on(
            "response", lambda r: self._log(self.network, f"{r.request.method} {r.url} -> {r.status}")
        )
        self.page.on(
            "requestfailed", lambda r: self._log(self.network, f"{r.method} {r.url} -> FAILED {r.failure}")
        )
        return self.page

    @staticmethod
    def _log(target: list[str], line: str) -> None:
        target.append(line[:500])
        del target[:-MAX_LOG]

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._browser = self._playwright = self.page = None


def _session(context: ToolContext) -> BrowserSession:
    if context.browser is None:
        context.browser = BrowserSession()
    session: BrowserSession = context.browser
    return session


async def _snapshot(page: Any) -> str:
    """The accessibility tree as compact text (roles, names, values): what a screen reader would 'see'."""
    try:
        tree = await page.locator("body").aria_snapshot()
    except Exception:
        tree = await page.inner_text("body")
    text = f"URL: {page.url}\nTitle: {await page.title()}\n{tree}"
    return text if len(text) <= SNAPSHOT_CHARS else text[:SNAPSHOT_CHARS] + "\n[… snapshot truncated …]"


class BrowserOpen(Tool):
    name = "browser_open"
    description = (
        "Open a page of the locally running app in a headless browser (e.g. its Swagger UI at "
        "http://127.0.0.1:<port>/swagger-ui) and return an accessibility snapshot. Local URLs only."
    )

    class Args(ToolArgs):
        url: str
        wait_for: str | None = Field(default=None, description="Optional text or CSS selector to wait for")

    def summary(self, args: BrowserOpen.Args) -> str:
        return f"browser open {args.url}"

    async def run(self, args: BrowserOpen.Args, context: ToolContext) -> ToolResult:
        problem = local_url(args.url)
        if problem:
            return ToolResult(ok=False, content=f"Not opened: {problem}.")
        try:
            page = await _session(context).ensure()
            response = await page.goto(args.url, wait_until="networkidle", timeout=30_000)
            if args.wait_for:
                selector = (
                    args.wait_for
                    if re.match(r"^[.#\[]|^\w+[.#\[]", args.wait_for)
                    else f"text={args.wait_for}"
                )
                await page.wait_for_selector(selector, timeout=15_000)
        except Exception as error:
            return ToolResult(ok=False, content=f"Browser error: {str(error).splitlines()[0]}")
        status = response.status if response is not None else "?"
        return ToolResult(ok=True, content=f"HTTP {status}\n" + await _snapshot(page))


class BrowserSnapshot(Tool):
    name = "browser_snapshot"
    read_only = True
    description = "The current page's accessibility snapshot (compact text)."

    class Args(ToolArgs):
        pass

    async def run(self, args: BrowserSnapshot.Args, context: ToolContext) -> ToolResult:
        session = _session(context)
        if session.page is None:
            return ToolResult(ok=False, content="No page is open: use browser_open first.")
        return ToolResult(ok=True, content=await _snapshot(session.page))


class BrowserClick(Tool):
    name = "browser_click"
    description = (
        "Click an element: a CSS selector, or visible text (e.g. 'GET /api/policies/', 'Try it out')."
    )

    class Args(ToolArgs):
        target: str

    def summary(self, args: BrowserClick.Args) -> str:
        return f"browser click {args.target}"

    async def run(self, args: BrowserClick.Args, context: ToolContext) -> ToolResult:
        session = _session(context)
        if session.page is None:
            return ToolResult(ok=False, content="No page is open: use browser_open first.")
        page = session.page
        try:
            locator = (
                page.locator(args.target)
                if re.match(r"^[.#\[]", args.target)
                else page.get_by_text(args.target).first
            )
            await locator.click(timeout=10_000)
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception as error:
            return ToolResult(ok=False, content=f"Click failed: {str(error).splitlines()[0]}")
        return ToolResult(ok=True, content=await _snapshot(page))


class BrowserFill(Tool):
    name = "browser_fill"
    description = "Type into an input: a CSS selector or the field's label/placeholder text."

    class Args(ToolArgs):
        target: str
        text: str

    def summary(self, args: BrowserFill.Args) -> str:
        return f"browser fill {args.target}"

    async def run(self, args: BrowserFill.Args, context: ToolContext) -> ToolResult:
        session = _session(context)
        if session.page is None:
            return ToolResult(ok=False, content="No page is open: use browser_open first.")
        page = session.page
        try:
            if re.match(r"^[.#\[]|^\w+[.#\[]", args.target):
                locator = page.locator(args.target)
            else:
                locator = page.get_by_label(args.target).or_(page.get_by_placeholder(args.target)).first
            await locator.fill(args.text, timeout=10_000)
        except Exception as error:
            return ToolResult(ok=False, content=f"Fill failed: {str(error).splitlines()[0]}")
        return ToolResult(ok=True, content="Filled.")


class BrowserScreenshot(Tool):
    name = "browser_screenshot"
    description = "Save a screenshot of the current page to .forge/screenshots (the user can view it)."

    class Args(ToolArgs):
        full_page: bool = False

    async def run(self, args: BrowserScreenshot.Args, context: ToolContext) -> ToolResult:
        session = _session(context)
        if session.page is None:
            return ToolResult(ok=False, content="No page is open: use browser_open first.")
        folder = context.workspace.jail.check(context.workspace.forge_dir / "screenshots")
        folder.mkdir(parents=True, exist_ok=True)
        path = context.workspace.jail.check(folder / f"shot-{time.strftime('%Y%m%d-%H%M%S')}.png")
        await session.page.screenshot(path=str(path), full_page=args.full_page)
        await context.emit(
            "notice", {"kind": "screenshot", "text": f"Screenshot saved: {path.name}", "path": str(path)}
        )
        return ToolResult(ok=True, content=f"Saved {path.relative_to(context.workspace.root).as_posix()}")


class BrowserConsole(Tool):
    name = "browser_console"
    read_only = True
    description = "Console messages and page errors recorded since the browser opened (latest last)."

    class Args(ToolArgs):
        pass

    async def run(self, args: BrowserConsole.Args, context: ToolContext) -> ToolResult:
        lines = _session(context).console
        return ToolResult(ok=True, content="\n".join(lines[-80:]) or "No console messages.")


class BrowserNetwork(Tool):
    name = "browser_network"
    read_only = True
    description = "Network requests the page made (method, URL, status), latest last."

    class Args(ToolArgs):
        pass

    async def run(self, args: BrowserNetwork.Args, context: ToolContext) -> ToolResult:
        lines = _session(context).network
        return ToolResult(ok=True, content="\n".join(lines[-80:]) or "No requests recorded.")


class BrowserClose(Tool):
    name = "browser_close"
    description = "Close the browser."

    class Args(ToolArgs):
        pass

    async def run(self, args: BrowserClose.Args, context: ToolContext) -> ToolResult:
        if context.browser is not None:
            await context.browser.close()
            context.browser = None
        return ToolResult(ok=True, content="Browser closed.")


class HttpRequest(Tool):
    name = "http_request"
    description = (
        "Call the locally running app's API (smoke test): method, URL on localhost, optional JSON body and "
        "headers. Returns status, headers and the (truncated) body."
    )

    class Args(ToolArgs):
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
        url: str
        json_body: Any = Field(default=None, alias="json")
        headers: dict[str, str] = Field(default_factory=dict)

    def summary(self, args: HttpRequest.Args) -> str:
        return f"{args.method} {args.url}"

    async def run(self, args: HttpRequest.Args, context: ToolContext) -> ToolResult:
        problem = local_url(args.url)
        if problem:
            return ToolResult(
                ok=False,
                content=f"Not sent: {problem.replace('browser tools only open', 'http_request only calls')}.",
            )
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
                response = await client.request(
                    args.method, args.url, json=args.json_body, headers=args.headers
                )
        except httpx.HTTPError as error:
            return ToolResult(
                ok=False, content=f"Request failed: {type(error).__name__}: {error}. Is the app running?"
            )
        body = response.text
        try:
            body = json.dumps(response.json(), indent=1)[:6000]
        except ValueError:
            body = body[:6000]
        interesting = {
            k: v for k, v in response.headers.items() if k.lower() in ("content-type", "location", "allow")
        }
        return ToolResult(
            ok=response.status_code < 500, content=f"HTTP {response.status_code}\n{interesting}\n{body}"
        )


def browser_tools() -> list[Tool]:
    return [
        BrowserOpen(),
        BrowserSnapshot(),
        BrowserClick(),
        BrowserFill(),
        BrowserScreenshot(),
        BrowserConsole(),
        BrowserNetwork(),
        BrowserClose(),
        HttpRequest(),
    ]
