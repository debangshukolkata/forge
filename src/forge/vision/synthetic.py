"""Synthetic eval samples (spec §13A.2 b), parameterised by document type — nothing here is specific to one
kind of document. A spec says which fields to write (with candidate values) and which regions to draw
(signature, diagram, stamp); each sample is rendered with handwriting-style fonts, then rotated, blurred and
noised, and its label (field values + region boxes, transformed with the rotation) is known exactly.

Synthetic samples test the pipeline and catch regressions; they are NOT proof of real-world accuracy, and every
label says `"synthetic": true` so reports keep the two apart.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HANDWRITING_FONTS = ["Inkfree.ttf", "segoesc.ttf", "LHANDW.TTF", "comic.ttf"]
PRINT_FONTS = ["arial.ttf", "segoeui.ttf", "calibri.ttf"]
PAGE = (1240, 1754)  # A4 at 150 dpi


@dataclass
class DocumentSpec:
    title: str
    fields: dict[str, list[str]]  # field name -> candidate values
    regions: list[str] = field(default_factory=lambda: ["signature"])  # signature | diagram | stamp
    unreadable_chance: float = 0.0  # probability a field is scribbled out (label: unreadable)
    rotation: float = 3.0  # max absolute degrees
    blur: float = 0.8
    noise: float = 0.02  # fraction of pixels flipped

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentSpec:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _font(names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _signature(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], rng: random.Random) -> None:
    x1, y1, x2, y2 = box
    points = []
    for step in range(60):
        t = step / 59
        x = x1 + t * (x2 - x1)
        y = (y1 + y2) / 2 + math.sin(t * rng.uniform(8, 14)) * (y2 - y1) * 0.35 + rng.uniform(-6, 6)
        points.append((x, y))
    draw.line(points, fill=(20, 30, 90), width=3, joint="curve")
    draw.line([(x1 + 10, y2 - 8), (x2 - 20, y2 - 12)], fill=(20, 30, 90), width=2)


def _diagram(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], rng: random.Random) -> None:
    x1, y1, x2, y2 = box
    draw.rectangle((x1 + 5, y1 + 5, x1 + (x2 - x1) // 3, y1 + (y2 - y1) // 3), outline="black", width=3)
    draw.ellipse((x2 - (x2 - x1) // 3, y2 - (y2 - y1) // 2, x2 - 5, y2 - 5), outline="black", width=3)
    draw.line(
        [(x1 + (x2 - x1) // 3, y1 + (y2 - y1) // 6), (x2 - (x2 - x1) // 6, y2 - (y2 - y1) // 2)],
        fill="black",
        width=3,
    )
    draw.polygon([(x1 + 20, y2 - 10), (x1 + 60, y2 - 10), (x1 + 40, y2 - 50)], outline="black")


def _stamp(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], rng: random.Random) -> None:
    draw.ellipse(box, outline=(170, 20, 30), width=5)
    font = _font(PRINT_FONTS, 22)
    draw.text(
        ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), "APPROVED", fill=(170, 20, 30), font=font, anchor="mm"
    )


DRAWERS = {
    "signature": (_signature, (330, 110)),
    "diagram": (_diagram, (360, 260)),
    "stamp": (_stamp, (220, 220)),
}


def generate(spec: DocumentSpec, out_dir: Path, count: int, seed: int = 7) -> list[Path]:
    """Writes samples/<name>.png and labels/<name>.json; returns the sample paths."""
    rng = random.Random(seed)
    (out_dir / "samples").mkdir(parents=True, exist_ok=True)
    (out_dir / "labels").mkdir(parents=True, exist_ok=True)
    written = []
    for number in range(1, count + 1):
        name = f"synthetic_{number:03d}.png"
        image, label = _render(spec, rng)
        image.save(out_dir / "samples" / name)
        label["sample"] = name
        (out_dir / "labels" / f"{Path(name).stem}.json").write_text(
            json.dumps(label, indent=1), encoding="utf-8"
        )
        written.append(out_dir / "samples" / name)
    return written


def _render(spec: DocumentSpec, rng: random.Random) -> tuple[Image.Image, dict[str, Any]]:
    page = Image.new("RGB", PAGE, (250, 249, 244))
    draw = ImageDraw.Draw(page)
    draw.text((PAGE[0] // 2, 90), spec.title, fill="black", font=_font(PRINT_FONTS, 44), anchor="mm")
    draw.line([(80, 140), (PAGE[0] - 80, 140)], fill="black", width=2)
    hand = _font(HANDWRITING_FONTS, rng.randint(34, 42))
    label_font = _font(PRINT_FONTS, 28)
    fields: dict[str, str] = {}
    unreadable: list[str] = []
    y = 200
    for name, values in spec.fields.items():
        value = rng.choice(values)
        draw.text((90, y), f"{name.replace('_', ' ').title()}:", fill="black", font=label_font)
        if rng.random() < spec.unreadable_chance:
            for _ in range(6):  # scribbled out
                draw.line(
                    [(420, y + rng.randint(0, 30)), (420 + rng.randint(150, 300), y + rng.randint(0, 30))],
                    fill=(30, 30, 30),
                    width=4,
                )
            unreadable.append(name)
        else:
            draw.text((420, y - 4), value, fill=(25, 35, 110), font=hand)
            fields[name] = value
        y += 90
    regions: list[dict[str, Any]] = []
    anchors = {
        "signature": (PAGE[0] - 460, PAGE[1] - 260),
        "diagram": (100, max(y + 40, 900)),
        "stamp": (PAGE[0] - 420, max(y + 60, 950)),
    }
    for kind in spec.regions:
        drawer, (width, height) = DRAWERS[kind]
        x, top = anchors[kind]
        x += rng.randint(-30, 30)
        top += rng.randint(-30, 30)
        box = (x, top, x + width, top + height)
        drawer(draw, box, rng)
        regions.append({"label": kind, "page": 1, "box": list(box)})
    angle = rng.uniform(-spec.rotation, spec.rotation)
    rotated = page.rotate(angle, expand=True, fillcolor=(250, 249, 244), resample=Image.Resampling.BICUBIC)
    regions = [{**r, "box": _rotate_box(r["box"], angle, PAGE, rotated.size)} for r in regions]
    if spec.blur:
        rotated = rotated.filter(ImageFilter.GaussianBlur(spec.blur))
    if spec.noise:
        pixels = rotated.load()
        assert pixels is not None
        for _ in range(int(rotated.width * rotated.height * spec.noise)):
            px, py = rng.randrange(rotated.width), rng.randrange(rotated.height)
            shade = rng.randint(0, 255)
            pixels[px, py] = (shade, shade, shade)
    label = {
        "fields": fields,
        "regions": regions,
        "unreadable": unreadable,
        "synthetic": True,
        "sensitive": False,
        "rotation": round(angle, 2),
    }
    return rotated, label


def _rotate_box(
    box: list[int], angle: float, size: tuple[int, int], new_size: tuple[int, int]
) -> list[float]:
    """PIL rotates counter-clockwise about the centre; with expand the canvas grows. Box corners follow."""
    cx, cy = size[0] / 2, size[1] / 2
    ncx, ncy = new_size[0] / 2, new_size[1] / 2
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)
    xs, ys = [], []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        dx, dy = x - cx, y - cy
        xs.append(ncx + dx * cos + dy * sin)
        ys.append(ncy - dx * sin + dy * cos)
    return [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]
