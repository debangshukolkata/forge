"""What the web tools can do on this machine, for `forge doctor` (D-209).

Nothing here is required: a missing piece means one stage of web_fetch is skipped, never that it fails. The
browser is proven with a real launch on a local page, so no network is needed."""

from __future__ import annotations

import importlib.metadata

from forge.doctor import CheckResult
from forge.tools.web_guard import WebPolicy
from forge.tools.web_render import RenderUnavailable, render_html


async def check_web_research() -> CheckResult:
    works: list[str] = []
    missing: list[str] = []
    try:
        html, _ = await render_html("data:text/html,<p>ok</p>", WebPolicy(), timeout_s=20)
        works.append("headless browser works" if "ok" in html else "headless browser started")
    except RenderUnavailable as unavailable:
        missing.append(f"pages that need JavaScript cannot be read: {unavailable}")
    for package, benefit, otherwise in (
        ("trafilatura", "Markdown extraction", "plain text extraction is used (pip install trafilatura)"),
        ("pypdfium2", "PDF reading", "PDFs cannot be read"),
    ):
        try:
            importlib.metadata.version(package)
            works.append(benefit)
        except importlib.metadata.PackageNotFoundError:
            missing.append(f"{package} is not installed: {otherwise}")
    return CheckResult("Web research", "warn" if missing else "ok", "; ".join([*works, *missing]))
