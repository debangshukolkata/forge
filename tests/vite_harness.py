"""Helper for the asset tests (TODO L1/L12): build a throwaway Vite + React + Tailwind v4 project from files, serve the
build, and run DebCraft's own style audit on it at 1280 and 375 px. It reuses the packages already installed in
`ui-react/node_modules` (work folders live inside `ui-react/.asset-work/`, which is git-ignored), so nothing is
downloaded. Tests that use it skip when `ui-react/node_modules` is missing."""

from __future__ import annotations

import functools
import http.server
import shutil
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UI_REACT = REPO / "ui-react"
WORK = UI_REACT / ".asset-work"
NODE = shutil.which("node")
VITE = UI_REACT / "node_modules" / "vite" / "bin" / "vite.js"
TSC = UI_REACT / "node_modules" / "typescript" / "bin" / "tsc"

VITE_CONFIG = """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({ plugins: [react(), tailwindcss()], build: { outDir: "dist", emptyOutDir: true } });
"""
TSCONFIG = """{ "compilerOptions": { "target": "ES2022", "lib": ["ES2022", "DOM", "DOM.Iterable"], "module": "ESNext",
  "moduleResolution": "bundler", "jsx": "react-jsx", "strict": true, "noEmit": true, "skipLibCheck": true,
  "types": [], "isolatedModules": true }, "include": ["src"] }
"""
INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title}</title><link rel="icon" href="data:," /></head>
<body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>
"""
MAIN_TSX = """import React from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
createRoot(document.getElementById("root")!).render(<App />);
"""


def available() -> bool:
    return bool(NODE) and VITE.is_file() and (UI_REACT / "node_modules" / "tailwindcss").is_dir()


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=300)


def build(name: str, files: dict[str, str], title: str = "Asset test") -> Path:
    """Writes the files (paths relative to the project root, e.g. `src/App.tsx`), type-checks and builds; returns dist/."""
    project = WORK / name
    shutil.rmtree(project, ignore_errors=True)
    (project / "src").mkdir(parents=True)
    (project / "vite.config.ts").write_text(VITE_CONFIG, encoding="utf-8")
    (project / "tsconfig.json").write_text(TSCONFIG, encoding="utf-8")
    (project / "index.html").write_text(INDEX_HTML.format(title=title), encoding="utf-8")
    (project / "src" / "main.tsx").write_text(MAIN_TSX, encoding="utf-8")
    (project / "src" / "vite-env.d.ts").write_text('/// <reference types="vite/client" />\n', encoding="utf-8")
    for relative, text in files.items():
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    typed = _run([NODE or "node", str(TSC), "-p", "tsconfig.json"], project)
    assert typed.returncode == 0, f"type errors:\n{typed.stdout[-3000:]}{typed.stderr[-500:]}"
    built = _run([NODE or "node", str(VITE), "build"], project)
    assert built.returncode == 0, f"vite build failed:\n{built.stdout[-3000:]}{built.stderr[-1500:]}"
    return project / "dist"


@contextmanager
def serve(directory: Path) -> Iterator[str]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()


async def audit(url: str, shots: Path | None = None, label: str = "page") -> dict[str, object]:
    """Opens the page in headless Edge at 1280 and 375 px; returns the audit text per width, console errors and any
    horizontal overflow. Screenshots (full page) go to `shots` when given."""
    from playwright.async_api import async_playwright

    from forge.tools.ui_audit import audit_page

    result: dict[str, object] = {"errors": [], "audit": {}, "overflow": {}}
    errors: list[str] = result["errors"]  # type: ignore[assignment]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        for width, height in ((1280, 800), (375, 800)):
            page = await browser.new_page(viewport={"width": width, "height": height})
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            # reveal-on-scroll content must be on screen to be audited and photographed
            await page.evaluate(
                "async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); "
                "await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }"
            )
            await page.wait_for_timeout(500)
            result["audit"][width] = await audit_page(page)  # type: ignore[index]
            result["overflow"][width] = await page.evaluate(  # type: ignore[index]
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            if shots is not None:
                shots.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(shots / f"{label}-{width}.png"), full_page=True)
            await page.close()
        await browser.close()
    return result
