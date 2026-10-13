"""D-337: a design shown as a picture is measured from its pixels, and a rendered slide is scored against it (P2.25)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

pytest.importorskip("pptx")
from PIL import Image, ImageDraw

from forge.slides.image_reader import (
    analyze_reference_image,
    compare_to_reference,
    describe_comparison,
    describe_reference,
)


def _png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def _dark_slide() -> Image.Image:
    image = Image.new("RGB", (1600, 900), (10, 14, 26))
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 90, 900, 190), fill=(240, 240, 245))  # a title bar in text colour
    draw.rectangle((100, 330, 700, 700), fill=(30, 120, 220))  # a blue block
    draw.rectangle((820, 330, 1500, 520), fill=(240, 160, 20))  # an amber block
    draw.rectangle((1440, 40, 1560, 110), fill=(250, 250, 250))  # a logo top right
    return image


def _light_slide() -> Image.Image:
    image = Image.new("RGB", (1600, 900), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 90, 900, 190), fill=(20, 20, 30))
    draw.rectangle((100, 330, 800, 700), fill=(200, 40, 60))
    return image


def test_a_dark_slide_is_read_with_its_colours_regions_and_corner_logo() -> None:
    design = analyze_reference_image(_png(_dark_slide()))
    assert design.dark and design.background.upper() == "#0A0E1A"
    assert "#1E78DC" in [c.upper() for c in design.accents] and design.brand["accent"].upper() == "#1E78DC"
    assert design.brand["background"] == design.background and "accent" in design.brand
    assert design.corners["top_right"] and not design.corners["bottom_left"]
    assert 3 <= len(design.regions) <= 6
    top = min(design.regions, key=lambda r: r.y)
    assert top.y < 15 and top.inches()["x"] < 3
    text = describe_reference(design, "ref.png")
    assert (
        "a dark slide" in text
        and "brand kit to use in an outline" in text
        and "Cannot be read from pixels" in text
    )


def test_a_light_slide_is_light_and_has_a_dark_text_colour() -> None:
    design = analyze_reference_image(_png(_light_slide()))
    assert not design.dark and design.background.upper().startswith("#F")
    assert design.text_colour.upper() != design.background.upper()
    assert any(c.upper().startswith("#C8") for c in design.accents)
    assert (
        len(design.regions) == 2 and max(r.w for r in design.regions) < 70
    )  # the title bar and the red block, not the whole slide


def test_an_exif_turned_photo_and_a_photo_of_a_screen_with_a_border_still_give_a_background() -> None:
    image = Image.new("RGB", (800, 600), (30, 30, 30))
    ImageDraw.Draw(image).rectangle(
        (60, 50, 740, 550), fill=(250, 250, 250)
    )  # a screen photographed: dark frame around a light slide
    design = analyze_reference_image(_png(image))
    assert design.background and design.palette


def test_comparison_scores_the_same_picture_high_and_different_ones_low_and_names_the_worst_cells() -> None:
    reference = _png(_dark_slide())
    same = compare_to_reference(reference, reference)
    assert same.score == 100.0 and same.palette_match == 1.0 and same.worst == []
    other = compare_to_reference(_png(_light_slide()), reference)
    assert other.score < 60 and other.worst and other.palette_match < 0.7
    close = _dark_slide()
    ImageDraw.Draw(close).rectangle(
        (820, 330, 1500, 520), fill=(240, 100, 20)
    )  # the amber block turned orange
    near = compare_to_reference(_png(close), reference)
    assert other.score < near.score < 100
    text = describe_comparison(near)
    assert "Match with the reference:" in text and "Aim for 80 or more" in text


async def test_the_tools(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.presentation import AnalyzeReferenceImage, CompareToReference
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_bytes("docs/ref.png", _png(_dark_slide()), "x")
    workspace.write_bytes("docs/mine.png", _png(_light_slide()), "x")
    context = ToolContext(workspace=workspace)
    analysed = await AnalyzeReferenceImage().run(AnalyzeReferenceImage.Args(path="docs/ref.png"), context)
    assert analysed.ok and "a dark slide" in analysed.content
    compared = await CompareToReference().run(
        CompareToReference.Args(rendered="docs/mine.png", reference="docs/ref.png"), context
    )
    assert compared.ok and "Match with the reference" in compared.content
    broken = await AnalyzeReferenceImage().run(AnalyzeReferenceImage.Args(path="docs/missing.png"), context)
    assert not broken.ok
