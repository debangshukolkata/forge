"""Which Gemini models can these credentials really use, in which region? Built for the question "do we have the 3rd generation?".

    .venv\\Scripts\\python scripts\\dev\\gemini_probe.py [--out gemini.txt] [--locations global,us-central1] [--models name1,name2]

model_options.py tried only one region (us-central1, or GOOGLE_CLOUD_LOCATION) and a short list of names. On Vertex AI the Gemini 3 models are served from the
`global` endpoint (not from us-central1), so "not available" there says nothing about the project. This script:
1. asks Vertex AI for the publisher models it lists in each region (names only);
2. sends one tiny text request, one picture request and, for image models, one image-generation request to every candidate name in every region;
3. prints a table of model, region, text, pictures, image output, and which regions to put in GOOGLE_CLOUD_LOCATION.

On a company network that inspects HTTPS it first switches Python to the Windows certificate store (the same setting DebCraft uses), because the `global` endpoint failed with
CERTIFICATE_VERIFY_FAILED without it (2026-10-14). It also probes every Gemini and Imagen name the region lists for the project, not only the names in this file.
It prints no key and no token. Needs the google-genai package and Google credentials (the office laptop's default credentials, GOOGLE_CLOUD_PROJECT optional).
Paste the output to the assistant."""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
import time
from typing import Any

TEXT_MODELS = [
    "gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-3.1-flash-preview", "gemini-3-pro", "gemini-3-flash",
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
]  # fmt: skip
IMAGE_MODELS = [
    "gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview", "gemini-2.5-flash-image", "gemini-2.5-flash-image-preview",
]  # fmt: skip
IMAGEN_MODELS = [
    "imagen-4.0-generate-001",
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-ultra-generate-001",
    "imagen-3.0-generate-002",
]
LOCATIONS = [
    "global",
    "us-central1",
    "us-east5",
    "us-east1",
    "europe-west4",
    "europe-west1",
    "asia-northeast1",
]
TIMEOUT_S = 90
SKIP_NAMES = (
    "live",
    "tts",
    "transcribe",
    "embedding",
    "translate",
    "robotics",
    "computer-use",
)  # not plain text or picture models


def red_square() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (220, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def say(lines: list[str], text: str = "") -> None:
    print(text, flush=True)
    lines.append(text)


def short(error: Exception) -> str:
    text = str(error)
    if "404" in text or "NOT_FOUND" in text:
        return "not available"
    if "403" in text or "PERMISSION_DENIED" in text:
        return "no permission"
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return "quota exhausted"
    return f"{type(error).__name__}: {text[:70]}"


def client_for(genai: Any, project: str, location: str) -> Any:
    return genai.Client(vertexai=True, project=project or None, location=location)


async def timed(call: Any) -> tuple[str, float]:
    started = time.time()
    try:
        await asyncio.wait_for(asyncio.to_thread(call), TIMEOUT_S)
        return "ok", time.time() - started
    except TimeoutError:
        return "timeout", time.time() - started
    except Exception as error:
        return short(error), time.time() - started


async def probe_text(client: Any, types: Any, name: str) -> tuple[str, str]:
    config = types.GenerateContentConfig(max_output_tokens=32)
    text, seconds = await timed(
        lambda: client.models.generate_content(
            model=name, contents="Reply with the single word: ready", config=config
        )
    )
    if text != "ok":
        return text, ""
    picture, _ = await timed(
        lambda: client.models.generate_content(
            model=name,
            contents=[
                "What colour is this square? One word.",
                types.Part.from_bytes(data=red_square(), mime_type="image/png"),
            ],
            config=config,
        )
    )
    return f"ok ({seconds:.1f}s)", picture


async def probe_image(client: Any, types: Any, name: str, imagen: bool) -> str:
    if imagen:
        result, seconds = await timed(
            lambda: client.models.generate_images(
                model=name,
                prompt="A small red paper lantern, flat illustration",
                config=types.GenerateImagesConfig(number_of_images=1),
            )
        )
    else:
        result, seconds = await timed(
            lambda: client.models.generate_content(
                model=name,
                contents="Draw a small red paper lantern, flat illustration.",
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
        )
    return f"ok ({seconds:.1f}s)" if result == "ok" else result


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--locations", default="", help="comma separated regions to try (default: a standard list)"
    )
    parser.add_argument("--models", default="", help="extra model names to try")
    args = parser.parse_args()
    lines: list[str] = []
    say(lines, "DebCraft Gemini probe (no keys or tokens are printed)")
    try:
        from forge.net import use_system_certificates

        say(lines, f"Windows certificate store in use: {use_system_certificates()}")
    except Exception as error:  # the probe still runs; certificate errors are then explained at the end
        say(lines, f"could not switch to the Windows certificate store ({type(error).__name__})")
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        say(lines, "the google-genai package is not installed here (pip install google-genai)")
        return
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    locations = [x.strip() for x in args.locations.split(",") if x.strip()] or list(
        dict.fromkeys([os.environ.get("GOOGLE_CLOUD_LOCATION", ""), *LOCATIONS])
    )
    locations = [x for x in locations if x]
    extra = [x.strip() for x in args.models.split(",") if x.strip()]
    say(lines, f"project: {project or 'from the default credentials'}   regions: {', '.join(locations)}")
    try:
        client_for(genai, project, locations[0])
    except Exception as error:
        say(lines, f"no usable Google credentials here: {short(error)}")
        return
    say(lines, "")
    say(lines, "== models each region lists for Google (names containing gemini, imagen, nano or banana) ==")
    listed: dict[str, list[str]] = {}
    for location in locations:
        try:
            client = client_for(genai, project, location)
            names = sorted(
                {
                    m.name.split("/")[-1]
                    for m in client.models.list(config={"page_size": 200})
                    if m.name and any(k in m.name.lower() for k in ("gemini", "imagen"))
                }
            )
            listed[location] = names
            say(
                lines,
                f"{location}: {len(names)} listed"
                + (
                    ": " + ", ".join(n for n in names if any(k in n for k in ("3", "image", "imagen")))
                    if names
                    else ""
                ),
            )
        except Exception as error:
            say(lines, f"{location}: could not list ({short(error)})")
    say(lines, "")
    say(lines, f"{'model':36} {'region':16} {'text':16} {'pictures':16} {'image output':16}")
    working: dict[str, list[str]] = {}
    known = {*TEXT_MODELS, *IMAGE_MODELS, *IMAGEN_MODELS, *extra}
    found_here: dict[
        str, list[str]
    ] = {}  # listed names the fixed lists do not know: tried in `global` and in the region that lists them
    for location, names in listed.items():
        for name in names:
            if name not in known and not any(word in name for word in SKIP_NAMES):
                found_here.setdefault(name, [])
                if location not in found_here[name]:
                    found_here[name].append(location)
    if found_here:
        say(lines, "")
        say(
            lines,
            "names the project lists that this script did not know, tried too: "
            + ", ".join(sorted(found_here)),
        )
    for name in [*TEXT_MODELS, *IMAGE_MODELS, *IMAGEN_MODELS, *extra, *sorted(found_here)]:
        is_image = name in IMAGE_MODELS or (name in found_here and "image" in name and "imagen" not in name)
        is_imagen = name in IMAGEN_MODELS or (name in found_here and "imagen" in name)
        where = (
            [x for x in locations if x == "global" or x in found_here[name]]
            if name in found_here
            else locations
        )
        for location in where:
            client = client_for(genai, project, location)
            text, pictures, image = "", "", ""
            if is_imagen:
                image = await probe_image(client, types, name, True)
                if image == "not available":
                    continue
            elif is_image:
                image = await probe_image(client, types, name, False)
                if image == "not available":
                    continue
                text, pictures = "", ""
            else:
                text, pictures = await probe_text(client, types, name)
                if text == "not available":
                    continue
            say(lines, f"{name:36} {location:16} {text:16} {pictures:16} {image:16}")
            if "ok" in (text, image) or text.startswith("ok") or image.startswith("ok"):
                working.setdefault(name, []).append(location)
    say(lines, "")
    say(lines, "== summary: models that answered, and where ==")
    for name, places in working.items():
        say(lines, f"{name}: {', '.join(places)}")
    third = [n for n in working if n.startswith(("gemini-3", "gemini-4"))]
    say(lines, "")
    say(
        lines,
        "3rd generation text models reachable: "
        + (
            ", ".join(third)
            if third
            else "none found in the regions tried (try --locations with your own regions, or ask the administrator to enable them)"
        ),
    )
    say(
        lines,
        "Use the region shown next to a model as GOOGLE_CLOUD_LOCATION (Gemini 3 models usually need `global`).",
    )
    if sum("CERTIFICATE_VERIFY_FAILED" in line for line in lines) >= 3:
        say(lines, "")
        say(
            lines,
            "Many calls failed with CERTIFICATE_VERIFY_FAILED: the company HTTPS inspection certificate is not trusted by this Python. Check the first lines (Windows certificate store in use: True?); if it says False, run `pip install truststore` in this environment and run the probe again.",
        )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
