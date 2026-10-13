"""Pictures that go into a deck (TODO P3.3, D-324): turned upright, shrunk to what a slide can show, compressed.

A phone photo is 4000 x 3000 pixels, 5 MB and rotated by an EXIF flag that PowerPoint ignores; ten of them make a deck that cannot be
mailed and a picture that lies on its side. A 13.33 inch slide at 192 dpi needs at most 2560 pixels on the long side, so anything larger
is shrunk to that. JPEGs are re-saved at quality 85 when they changed or are large; PNGs keep their format (sharp edges, transparency)
except large photo-like ones without transparency, which become JPEG. Files that are not JPEG or PNG (and anything that fails) are
returned unchanged."""

from __future__ import annotations

import io

MAX_EDGE = 2560
LARGE_BYTES = 1_500_000
JPEG_QUALITY = 85
PHOTO_COLOURS = 5000  # a picture with more distinct colours than this is a photo, not a diagram
MAX_PIXELS = 120_000_000  # more than this is refused as a decompression bomb and left alone


def prepare_image(data: bytes) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return data
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ("JPEG", "PNG") or source.width * source.height > MAX_PIXELS:
                return data
            picture = ImageOps.exif_transpose(source)
            turned = picture is not source and source.getexif().get(0x0112, 1) != 1
            picture.load()
            shrink = max(picture.size) > MAX_EDGE
            if shrink:
                scale = MAX_EDGE / max(picture.size)
                picture = picture.resize(
                    (max(1, round(picture.width * scale)), max(1, round(picture.height * scale))),
                    Image.Resampling.LANCZOS,
                )
            large = len(data) > LARGE_BYTES
            if not (turned or shrink or large):
                return data
            out = io.BytesIO()
            if source.format == "JPEG":
                picture.convert("RGB").save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
            else:
                transparent = "A" in picture.getbands() or "transparency" in picture.info
                photo = picture.convert("RGB").getcolors(maxcolors=PHOTO_COLOURS) is None
                if photo and not transparent:
                    picture.convert("RGB").save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
                else:
                    picture.save(out, "PNG", optimize=True)
            smaller = out.getvalue()
            return smaller if (turned or shrink or len(smaller) < len(data)) else data
    except Exception:  # a damaged or unusual file is the builder's problem to report, not this step's
        return data
