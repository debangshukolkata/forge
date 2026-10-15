"""A synthetic photo of a handwritten prescription, with a known signature (no real person, no real data).

    python scripts/overnight/make_signature_sample.py <out-folder> [--seed 7] [--name prescription.jpg]

Writes the photo and `<name>.truth.json` (the signature's bounding box and the number of ink pixels, measured on the signature drawn alone). The photo is a portrait page
with paper noise, folds, a printed header, a few lines of handwriting and a looping signature at the bottom right in blue ink: the same ingredients as a phone photo of a
real prescription, so the task "find the signature and cut it out" is a fair test. Only Pillow is needed."""

from __future__ import annotations

import argparse
import json
import math
import random
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 736, 1308
INK = (58, 52, 150)


def stroke(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], width: int, fill: object) -> None:
    for first, second in pairwise(points):
        draw.line([first, second], fill=fill, width=width)
    for x, y in points[:: max(1, len(points) // 60)]:
        draw.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=fill)


def wobble_line(
    rng: random.Random, x0: float, y0: float, length: float, height: float
) -> list[tuple[float, float]]:
    """A handwriting-like line: a baseline with loops and tall strokes."""
    points = []
    steps = int(length / 4)
    for step in range(steps):
        t = step / steps
        x = x0 + t * length + 6 * math.sin(t * 40 + rng.random())
        y = (
            y0
            + height * 0.35 * math.sin(t * 55) * (0.4 + 0.6 * math.sin(t * 7) ** 2)
            + rng.uniform(-1.2, 1.2)
        )
        points.append((x, y))
    return points


def signature_points(rng: random.Random, cx: float, cy: float, scale: float) -> list[tuple[float, float]]:
    """A looping scrawl with a long tail: a spiral, a vertical flourish and a sweeping line."""
    points: list[tuple[float, float]] = []
    for step in range(220):  # the loops
        t = step / 220 * 4.5 * math.pi
        r = scale * (0.25 + 0.45 * (1 - step / 260))
        points.append((cx + r * math.cos(t) * 0.85, cy + r * math.sin(t) * 1.25 - step * 0.06 * scale / 40))
    top = points[-1]
    for step in range(60):  # the downstroke
        t = step / 60
        points.append((top[0] + 8 * math.sin(t * 6), top[1] + t * 1.6 * scale))
    base = points[-1]
    for step in range(120):  # the tail
        t = step / 120
        points.append((base[0] + t * 2.6 * scale, base[1] - t * 0.9 * scale + 10 * math.sin(t * 5) * (1 - t)))
    return points


def make(out: Path, seed: int = 7, name: str = "prescription.jpg") -> dict[str, object]:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (WIDTH, HEIGHT), (214, 211, 203))
    noise = Image.effect_noise((WIDTH, HEIGHT), 14).convert("RGB")
    page = Image.blend(page, noise, 0.10)
    draw = ImageDraw.Draw(page)
    try:
        title = ImageFont.truetype("arial.ttf", 34)
        small = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        title = small = ImageFont.load_default()
    draw.text((36, 52), "Riverside Family Clinic", fill=INK, font=title)  # a fictional printed header
    draw.text((36, 98), "General physician and paediatrics", fill=INK, font=small)
    draw.text((520, 60), "Dr. A. Sample", fill=INK, font=small)
    draw.text((520, 84), "MBBS, MD", fill=INK, font=small)
    draw.line([(30, 150), (700, 146)], fill=INK, width=2)
    for number in range(7):  # handwritten lines
        y = 230 + number * 92 + rng.uniform(-6, 6)
        stroke(draw, wobble_line(rng, 60 + rng.uniform(0, 40), y, rng.uniform(260, 520), 36), 3, INK)
    cx, cy, scale = rng.uniform(540, 575), rng.uniform(1010, 1040), rng.uniform(50, 68)
    points = signature_points(rng, cx, cy, scale)
    stroke(draw, points, 3, INK)
    for fold in (430, 880):  # two folds: a light and a dark band
        for offset in range(-6, 7):
            shade = 30 - abs(offset) * 4
            draw.line(
                [(0, fold + offset), (WIDTH, fold + offset + 6)],
                fill=(214 - shade, 211 - shade, 203 - shade),
                width=1,
            )
    vignette = Image.radial_gradient("L").resize((WIDTH, HEIGHT))
    page = ImageChops.multiply(
        page, Image.merge("RGB", [ImageChops.invert(vignette).point(lambda v: 255 - v // 5)] * 3)
    )
    page = page.filter(ImageFilter.GaussianBlur(0.9))
    page.save(out / name, "JPEG", quality=82)
    mask = Image.new("L", (WIDTH, HEIGHT), 0)  # the signature alone, to measure the truth
    stroke(ImageDraw.Draw(mask), points, 3, 255)
    box = mask.getbbox() or (0, 0, 0, 0)
    truth = {
        "bbox": list(box),
        "width": box[2] - box[0],
        "height": box[3] - box[1],
        "ink_pixels": mask.point(lambda value: 1 if value > 127 else 0).histogram()[1],
        "image": [WIDTH, HEIGHT],
    }
    (out / f"{name}.truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
    return truth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--name", default="prescription.jpg")
    args = parser.parse_args()
    print(json.dumps(make(Path(args.out), args.seed, args.name)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
