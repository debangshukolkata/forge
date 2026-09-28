"""Image utilities for Forge's vision tools (spec §13A.1): info, operations, box overlays, comparison, and
preparing an image for the vision model (EXIF-oriented, downscaled, PNG/JPEG data URL). Pillow only."""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

MAX_MODEL_SIDE = 2048  # the vision models' practical limit; larger images are downscaled first
Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


def open_image(path: Path) -> Image.Image:
    image = Image.open(path)
    image.load()
    return ImageOps.exif_transpose(image) or image


def info(path: Path) -> dict[str, Any]:
    image = Image.open(path)
    exif = image.getexif()
    return {
        "path": str(path),
        "format": image.format,
        "size": list(image.size),
        "mode": image.mode,
        "dpi": list(image.info["dpi"]) if "dpi" in image.info else None,
        "exif_orientation": exif.get(0x0112),
        "frames": getattr(image, "n_frames", 1),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
    }


def apply_ops(image: Image.Image, ops: list[dict[str, Any]]) -> Image.Image:
    """crop{box}, rotate{degrees}, deskew{}, resize{width?,height?,scale?}, grayscale, threshold{level},
    pad{pixels}, autocontrast, sharpen, denoise."""
    for op in ops:
        kind = op.get("op")
        if kind == "crop":
            x1, y1, x2, y2 = (int(v) for v in op["box"])
            image = image.crop((max(x1, 0), max(y1, 0), min(x2, image.width), min(y2, image.height)))
        elif kind == "rotate":
            image = image.rotate(float(op["degrees"]), expand=True, fillcolor="white")
        elif kind == "deskew":
            image = image.rotate(estimate_skew(image), expand=True, fillcolor="white")
        elif kind == "resize":
            scale = float(op.get("scale") or 0)
            width = int(op.get("width") or (image.width * scale if scale else image.width))
            height = int(
                op.get("height") or (image.height * scale if scale else image.height * width / image.width)
            )
            image = image.resize((max(width, 1), max(height, 1)), Image.Resampling.LANCZOS)
        elif kind == "grayscale":
            image = ImageOps.grayscale(image)
        elif kind == "threshold":
            level = int(op.get("level", 160))
            image = ImageOps.grayscale(image).point(lambda v, level=level: 255 if v > level else 0)
        elif kind == "pad":
            image = ImageOps.expand(image, border=int(op.get("pixels", 10)), fill="white")
        elif kind == "autocontrast":
            image = ImageOps.autocontrast(image.convert("RGB"))
        elif kind == "sharpen":
            image = image.filter(ImageFilter.SHARPEN)
        elif kind == "denoise":
            image = image.filter(ImageFilter.MedianFilter(3))
        else:
            raise ValueError(f"unknown image op {kind!r}")
    return image


def estimate_skew(image: Image.Image, max_degrees: float = 8.0, step: float = 0.5) -> float:
    """Projection-profile deskew: the angle whose rotated text rows are sharpest (highest row variance)."""
    small = ImageOps.grayscale(image)
    small.thumbnail((600, 600))
    inverted = ImageOps.invert(small)
    best_angle, best_score = 0.0, -1.0
    angle = -max_degrees
    while angle <= max_degrees:
        rotated = inverted.rotate(angle, expand=False, fillcolor=0)
        width = rotated.width
        data = rotated.tobytes()
        rows = [sum(data[r * width : (r + 1) * width]) for r in range(rotated.height)]
        mean = sum(rows) / len(rows)
        score = sum((v - mean) ** 2 for v in rows)
        if score > best_score:
            best_angle, best_score = angle, score
        angle += step
    return best_angle


COLOURS = ["#e11d48", "#2563eb", "#16a34a", "#d97706", "#7c3aed", "#0891b2"]


def draw_boxes(image: Image.Image, boxes: list[dict[str, Any]]) -> Image.Image:
    """boxes: [{box: [x1,y1,x2,y2], label?, colour?}] drawn on a copy (predicted vs expected overlays)."""
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    width = max(2, round(max(canvas.size) / 400))
    for index, item in enumerate(boxes):
        colour = item.get("colour") or COLOURS[index % len(COLOURS)]
        x1, y1, x2, y2 = (float(v) for v in item["box"])
        draw.rectangle((x1, y1, x2, y2), outline=colour, width=width)
        label = str(item.get("label") or "")
        if label:
            draw.text((x1 + 3, max(y1 - 14, 0)), label, fill=colour)
    return canvas


def iou(a: Box, b: Box) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def compare(a: Image.Image, b: Image.Image) -> tuple[Image.Image, float]:
    """Side-by-side composite and the fraction of 'ink' pixels shared (both images binarised, same size)."""
    size = (max(a.width, b.width), max(a.height, b.height))
    left, right = (ImageOps.pad(im.convert("L"), size, color=255) for im in (a, b))
    ink_left, ink_right = (im.point(lambda v: 255 if v < 128 else 0) for im in (left, right))
    both = ImageChops.multiply(ink_left, ink_right)
    either = ImageChops.lighter(ink_left, ink_right)
    overlap = both.histogram()[255] / max(1, either.histogram()[255])  # ink pixels are 255 after binarising
    composite = Image.new("RGB", (size[0] * 2 + 10, size[1]), "white")
    composite.paste(left.convert("RGB"), (0, 0))
    composite.paste(right.convert("RGB"), (size[0] + 10, 0))
    return composite, overlap


def for_model(image: Image.Image, region: Box | None = None) -> tuple[str, dict[str, Any]]:
    """A data URL the vision model accepts, plus what was sent (for the transcript log)."""
    if region is not None:
        image = image.crop(tuple(int(v) for v in region))  # type: ignore[arg-type]
    image = image.convert("RGB")
    original = image.size
    image.thumbnail((MAX_MODEL_SIDE, MAX_MODEL_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    data = buffer.getvalue()
    meta = {
        "sent_size": list(image.size),
        "original_size": list(original),
        "sha256": hashlib.sha256(data).hexdigest()[:16],
    }
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii"), meta


def save(image: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path
