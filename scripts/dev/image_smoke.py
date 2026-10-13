r"""Live check of generate_image on Vertex AI. Run on a machine with Google ADC (the office laptop); it cannot pass without credentials.

    (optional) set GOOGLE_CLOUD_PROJECT=<project>  &  set GOOGLE_CLOUD_LOCATION=us-central1
    (optional) set GEMINI_IMAGE_MODEL=gemini-2.5-flash-image   (or an imagen-... model)
    .venv\Scripts\python scripts\dev\image_smoke.py

Writes smoke-picture.png next to where you run it and prints OK or the reason it failed.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from forge.config import Secrets, load_secrets
from forge.toolkit.base import ToolContext
from forge.tools.imagegen import GenerateImage, model_name
from forge.workspace.create import create_workspace


async def main() -> int:
    secrets: Secrets = load_secrets()
    print(
        f"model: {model_name(secrets)}  project: {secrets.get('GOOGLE_CLOUD_PROJECT') or '(from credentials)'}"
    )
    folder = Path(tempfile.mkdtemp())
    (folder / "repo" / "app").mkdir(parents=True)
    (folder / "repo" / "app" / "readme.md").write_text("x", encoding="utf-8")
    workspace = create_workspace(folder / "repo", folder / "ws", "app")
    result = await GenerateImage().run(
        GenerateImage.Args(
            prompt="A flat, calm illustration of a vineyard on a hillside at dawn, soft green and gold, no text",
            path="smoke.png",
        ),
        ToolContext(workspace=workspace, secrets=secrets),
    )
    print(("OK   " if result.ok else "FAIL ") + result.content)
    if result.ok:
        target = Path.cwd() / "smoke-picture.png"
        target.write_bytes(workspace.path_of("smoke.png").read_bytes())
        print(f"picture: {target}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(asyncio.run(main()))
