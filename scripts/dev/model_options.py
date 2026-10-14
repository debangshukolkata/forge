"""Which models can this machine's keys reach? (for choosing the design-role model, TODO DS8)

    .venv\\Scripts\\python scripts\\dev\\model_options.py             (reads the .env file the way DebCraft does; prints no key)
    .venv\\Scripts\\python scripts\\dev\\model_options.py --out report.txt

It asks each provider what it offers, then sends one tiny request to every candidate to see what really answers, how fast, and whether pictures are
accepted (the design critic and the judge need vision). Azure: deployment names are the ones you made in the portal, so it tries the names in your
`.env` and the usual ones (gpt-5, gpt-4.1, gpt-4o, o3 ...); add your own with --azure-names a,b,c. Gemini: with GEMINI_API_KEY it lists the models of
the Gemini API; with Google credentials (office laptop) it tries Vertex AI (GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION). Paste the output to
the assistant: it contains deployment and model names only, never a key.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import os
import sys
import time
from typing import Any

import httpx

from forge.config import load_secrets

AZURE_COMMON = [
    "gpt-5", "gpt-5-mini", "gpt-5-chat", "gpt-5.1", "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o3", "o4-mini", "o1", "gpt-4", "gpt-35-turbo",
]  # fmt: skip
GEMINI_COMMON = [
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-2.5-flash-lite",
]  # fmt: skip
TIMEOUT = 40.0


def red_square() -> str:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (220, 0, 0)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def say(lines: list[str], text: str = "") -> None:
    print(text, flush=True)
    lines.append(text)


async def azure_chat(
    client: httpx.AsyncClient, endpoint: str, version: str, key: str, name: str, picture: bool
) -> tuple[str, float]:
    """(result, seconds) of one tiny request to deployment `name`: 'ok', 'ok (no pictures)', 'no such deployment', or the error."""
    started = time.time()
    content: Any = "Reply with the single word: ready"
    if picture:
        content = [
            {"type": "text", "text": "What colour is this square? One word."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + red_square()}},
        ]
    url = f"{endpoint.rstrip('/')}/openai/deployments/{name}/chat/completions?api-version={version}"
    for limit_key in ("max_completion_tokens", "max_tokens"):
        body = {"messages": [{"role": "user", "content": content}], limit_key: 64}
        response = await client.post(url, headers={"api-key": key}, json=body)
        if response.status_code == 200:
            return "ok", time.time() - started
        text = response.text[:300]
        if response.status_code == 404 or "DeploymentNotFound" in text:
            return "no such deployment", time.time() - started
        if "max_tokens" in text and limit_key == "max_tokens":
            continue
        if "max_completion_tokens" in text and limit_key == "max_completion_tokens":
            continue
        if "unsupported" in text.lower() and "image" in text.lower():
            return "no pictures", time.time() - started
        return f"HTTP {response.status_code}: {text[:160]}", time.time() - started
    return "error", time.time() - started


async def azure(lines: list[str], extra: list[str]) -> None:
    secrets = load_secrets()
    endpoint = secrets.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    key = secrets.get("AZURE_OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY", "")
    version = secrets.get("AZURE_OPENAI_API_VERSION") or os.environ.get(
        "AZURE_OPENAI_API_VERSION", "2024-10-21"
    )
    say(lines, "== Azure OpenAI ==")
    if not endpoint or not key:
        say(lines, "not configured here (AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY missing)")
        return
    say(lines, f"resource: {endpoint}   api-version: {version}")
    configured = [
        secrets.get(n) or os.environ.get(n, "")
        for n in ("AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_SECONDARY_DEPLOYMENT", "AZURE_FALLBACK_DEPLOYMENT")
    ]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        listed: list[str] = []
        for listing in ("2022-12-01", "2023-03-15-preview", version):
            try:
                response = await client.get(
                    f"{endpoint.rstrip('/')}/openai/deployments?api-version={listing}",
                    headers={"api-key": key},
                )
            except httpx.HTTPError as error:
                say(lines, f"listing deployments failed: {type(error).__name__}")
                break
            if response.status_code == 200:
                for item in response.json().get("data", []):
                    listed.append(item.get("id", "?"))
                    say(
                        lines,
                        f"  deployment {item.get('id')}: model {item.get('model')}, status {item.get('status')}",
                    )
                break
        if not listed:
            say(lines, "the resource does not list its deployments to a key (normal): trying names instead")
        names = list(dict.fromkeys([n for n in [*configured, *listed, *extra, *AZURE_COMMON] if n]))
        say(lines, f"{'deployment':28} {'text':22} {'pictures':22}")
        for name in names:
            text, seconds = await azure_chat(client, endpoint, version, key, name, False)
            if text != "ok":
                if configured.count(name) or name in listed:
                    say(lines, f"{name:28} {text:22}")
                continue
            picture, _ = await azure_chat(client, endpoint, version, key, name, True)
            marker = "  <- configured" if name in configured else ""
            say(lines, f"{name:28} {f'ok ({seconds:.1f}s)':22} {picture:22}{marker}")


async def gemini(lines: list[str]) -> None:
    secrets = load_secrets()
    key = secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    say(lines, "")
    say(lines, "== Gemini ==")
    models: list[str] = []
    if key:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                headers={"x-goog-api-key": key},
            )
            if response.status_code == 200:
                models = [
                    m["name"].removeprefix("models/")
                    for m in response.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                say(
                    lines,
                    f"Gemini API (API key): {len(models)} models can generate text; the strongest families here:",
                )
                for name in [
                    m
                    for m in models
                    if m.startswith("gemini")
                    and not any(x in m for x in ("embedding", "tts", "image", "live", "vision", "robotics"))
                ][:14]:
                    say(lines, f"  {name}")
            else:
                say(lines, f"Gemini API answered HTTP {response.status_code}: {response.text[:160]}")
    else:
        say(lines, "no GEMINI_API_KEY here")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or secrets.get("GOOGLE_CLOUD_PROJECT") or ""
    location = (
        os.environ.get("GOOGLE_CLOUD_LOCATION") or secrets.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
    )
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        say(
            lines,
            "Vertex AI: the google-genai package is not installed here (pip install google-genai) - skipped",
        )
        return
    try:
        client = (
            genai.Client(vertexai=True, project=project or None, location=location)
            if (project or not key)
            else genai.Client(api_key=key)
        )
    except Exception as error:
        say(
            lines,
            f"Vertex AI: no usable Google credentials here ({type(error).__name__}: {str(error)[:120]})",
        )
        return
    say(lines, f"Vertex AI (project {project or 'from credentials'}, {location}): trying the usual models")
    say(lines, f"{'model':28} {'text':22} {'pictures':22}")
    for name in [*GEMINI_COMMON, *[m for m in models if m not in GEMINI_COMMON][:0]]:
        outcome = []
        for picture in (False, True):
            started = time.time()
            try:
                parts: list[Any] = [
                    "What colour is this square? One word."
                    if picture
                    else "Reply with the single word: ready"
                ]
                if picture:
                    parts.append(
                        types.Part.from_bytes(data=base64.b64decode(red_square()), mime_type="image/png")
                    )
                await asyncio.to_thread(
                    client.models.generate_content,
                    model=name,
                    contents=parts,
                    config=types.GenerateContentConfig(max_output_tokens=32),
                )
                outcome.append(f"ok ({time.time() - started:.1f}s)")
            except Exception as error:
                outcome.append(
                    "not available"
                    if "404" in str(error) or "NOT_FOUND" in str(error)
                    else f"{type(error).__name__}: {str(error)[:60]}"
                )
                if not picture:
                    outcome.append("")
                    break
        say(lines, f"{name:28} {outcome[0]:22} {outcome[1] if len(outcome) > 1 else '':22}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--azure-names", default="", help="extra Azure deployment names, comma separated")
    parser.add_argument("--out", default="", help="also write the report to this file")
    args = parser.parse_args()
    lines: list[str] = []
    say(lines, "DebCraft model options (no keys are printed)")
    await azure(lines, [n.strip() for n in args.azure_names.split(",") if n.strip()])
    await gemini(lines)
    say(lines, "")
    say(
        lines,
        "Reading it: a deployment that answers with text AND pictures can be the design role (builder, critic and judge all need pictures).",
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
