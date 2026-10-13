"""Template probe (D-296): try a corporate template and report how DebCraft reads and uses it, so a real template can be checked on the
laptop that has it without sending the template itself. `forge template-probe company.potx` writes a folder with:

- `report.txt`: the template as DebCraft reads it (size, theme, fonts, layouts, sample slides and their slots) and a list of
  things that look wrong or unsupported;
- `probe-deck.pptx`: a deck built on the template with placeholder text: every sample slide filled once with normal text and once
  with long text, each ordinary layout matched automatically, and slides the template has no sample for (chart, table, diagram);
- pictures (PowerPoint, Windows) of the template's own slides and of the probe deck, plus contact sheets, and PowerPoint's
  measurement of text that does not fit;
- `probe.json`: the same findings as data.

With `hide_text` the report leaves out the words on the template's slides (it keeps kinds, sizes and counts). The pictures show the
template, so look at them before sending them anywhere."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.slides.build import SlidesUnavailable, build_deck
from forge.slides.errors import BuildError
from forge.slides.spec import parse_deck
from forge.slides.template import analyze_template, describe_template
from forge.slides.template_build import _open
from forge.slides.template_samples import Sample, analyze_samples, describe_samples
from forge.slides.validate import validate_package

SHORT_HEADING = "Short heading"
SHORT_TEXT = "A sentence of about ten words that explains the point."
LONG_HEADING = "A much longer heading that runs over two lines on a narrow card"
LONG_TEXT = (
    "This is deliberately long text, the kind a real deck sometimes has, so the probe can show how the template's boxes cope when "
    "there are many more words than the sample slide was drawn for. " * 2
)
ORDINARY = (
    {"layout": "title", "title": "Probe deck title", "subtitle": "A subtitle for the probe"},
    {"layout": "section", "title": "A section divider", "subtitle": "What this part covers"},
    {"layout": "bullets", "title": "Three short points make the slide", "bullets": ["First short point", "Second short point", {"text": "Third point", "sub": ["with a detail"]}]},
    {"layout": "two_column", "title": "Two sides compared side by side", "left": {"heading": "Left", "bullets": ["One", "Two"]}, "right": {"heading": "Right", "bullets": ["One", "Two"]}},
    {"layout": "stats", "title": "Numbers that matter this quarter", "items": [{"value": "42%", "label": "growth"}, {"value": "1.2M", "label": "users"}]},
    {"layout": "cards", "title": "Three reasons customers choose us", "items": [{"heading": SHORT_HEADING, "text": SHORT_TEXT}] * 3},
    {"layout": "steps", "title": "The plan takes four steps", "steps": [{"heading": "Plan", "text": "Agree scope"}, {"heading": "Build"}, {"heading": "Pilot"}, {"heading": "Launch"}]},
    {"layout": "chart", "title": "Users doubled since January", "kind": "column", "categories": ["Jan", "Feb", "Mar"], "series": [{"name": "Users", "values": [1, 2, 3]}]},
    {"layout": "table", "title": "Numbers by region at a glance", "columns": ["Region", "Revenue"], "rows": [["North", 120], ["South", 95]]},
    {"layout": "freeform", "title": "A diagram drawn in the template's theme", "elements": [{"type": "diagram", "recipe": "process", "x": 0.8, "y": 2.4, "w": 11.7, "h": 2.6, "items": ["Plan", "Build", "Ship"]}]},
    {"layout": "closing", "title": "Thank you", "subtitle": "name@example.com"},
)  # fmt: skip


@dataclass
class ProbeResult:
    folder: Path
    issues: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    slides_built: int = 0
    slides_failed: int = 0


def _fill_for(sample: Sample, long: bool) -> dict[str, Any]:
    """Placeholder content for every slot a sample has (normal or long text)."""
    heading, text = (LONG_HEADING, LONG_TEXT) if long else (SHORT_HEADING, SHORT_TEXT)
    fills: dict[str, Any] = {}
    roles = {s.role for s in sample.slots if not s.fixed}
    if "title" in roles:
        fills["title"] = (
            "Probe title " + ("with many more words than the sample title had " if long else "")
        ).strip()
    if "subtitle" in roles:
        fills["subtitle"] = text[:60] if not long else text
    if sample.items:
        parts = sample.items[0].parts
        fills["items"] = [
            {
                part: (
                    "1"
                    if part == "number" and not long
                    else "42%"
                    if part == "number"
                    else heading
                    if part == "heading"
                    else text
                )
                for part in parts
            }
            for _ in sample.items
        ]
    else:
        body = sample.slot("body") or next(
            (s for s in sample.slots if s.role == "text" and not s.fixed and s.paragraphs >= 2), None
        )
        if body is not None:
            lines = [text] * (6 if long else max(body.paragraphs, 3))
            fills[f"slot:{body.id}"] = lines
        for slot in sample.slots:
            if (
                slot.role == "text"
                and not slot.fixed
                and body is not None
                and slot.id != body.id
                and f"slot:{slot.id}" not in fills
            ):
                fills[f"slot:{slot.id}"] = heading if len(slot.text.split()) <= 4 else text
    return fills


def _hide(text: str) -> str:
    """The report without the template's own words: quoted slot texts become their length."""
    return re.sub(
        r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"",
        lambda m: f"<{len(m.group(1) or m.group(2))} chars>",
        text,
    )


def _issues(prs: Any, info: Any, samples: list[Sample]) -> list[str]:
    found: list[str] = []
    if not info.widescreen:
        found.append(
            f"The template is {info.width:.1f} x {info.height:.1f} in, not 16:9: new decks cannot be built on it (edit_presentation only)."
        )
    for role in ("title", "content", "title_only"):
        if role not in info.roles:
            found.append(
                f"No layout of the kind '{role}' was recognised: DebCraft falls back to another layout for those slides."
            )
    odd = [layout.name for layout in info.layouts if layout.role == "other"]
    if odd:
        found.append(f"{len(odd)} layouts were not recognised (kind 'other'): {', '.join(odd[:8])}")
    if not samples:
        found.append("The template has no sample slides: slides are made from its layouts only.")
    for sample in samples:
        if sample.kind == "other":
            found.append(
                f"Sample slide {sample.number} could not be classified (kind 'other'): it can still be used with template_slide."
            )
        if sample.charts or sample.tables:
            found.append(
                f"Sample slide {sample.number} holds a chart or table: it cannot be copied; those slides are built on a layout instead."
            )
    if samples and not any(s.fixed for sample in samples for s in sample.slots):
        found.append(
            "No company text repeated across the samples was found (a footer line, a confidentiality note): fine if there is none."
        )
    return found


def _try_slide(slide: dict[str, Any], template: bytes, label: str) -> tuple[bool, str]:
    outline = {"title": "probe", "template": "template", "slides": [slide]}
    try:
        built = build_deck(parse_deck(json.dumps(outline)), lambda name: template)
    except (BuildError, SlidesUnavailable, ValueError) as error:
        return False, f"{label}: {error}"
    problems = validate_package(built.data)
    warnings = [w for s in built.slides for w in s.warnings]
    return not problems, f"{label}: " + ("; ".join(problems + warnings) or "ok")


def run_probe(template_path: Path, folder: Path, hide_text: bool = False) -> ProbeResult:
    result = ProbeResult(folder)
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    data = template_path.read_bytes()
    prs = _open(data)
    info = analyze_template(prs)
    samples = analyze_samples(prs)
    report = describe_template(info, template_path.name) + "\n\n" + describe_samples(samples)
    result.issues += _issues(prs, info, samples)

    slides: list[tuple[str, dict[str, Any]]] = [(f"ordinary {s['layout']}", dict(s)) for s in ORDINARY]
    for sample in samples:
        if sample.charts or sample.tables:
            continue
        for long in (False, True):
            slides.append(
                (
                    f"sample {sample.number} [{sample.kind}] {'long text' if long else 'normal text'}",
                    {"layout": "template_slide", "source": sample.number, "fill": _fill_for(sample, long)},
                )
            )
    built_slides: list[dict[str, Any]] = []
    built_labels: list[str] = []
    notes = []
    for label, slide in slides:
        ok, note = _try_slide(slide, data, label)
        notes.append(("  OK  " if ok else "  FAIL ") + note)
        if ok:
            built_slides.append(slide)
            built_labels.append(label)
        else:
            result.slides_failed += 1
            result.issues.append(f"probe slide failed: {note}")
    result.slides_built = len(built_slides)
    report += "\n\nProbe slides (each built on its own first):\n" + "\n".join(notes)

    deck_path = folder / "probe-deck.pptx"
    if built_slides:
        outline = {
            "title": "Template probe",
            "subtitle": "placeholder content",
            "template": "template",
            "slides": built_slides,
        }
        deck_path.write_bytes(build_deck(parse_deck(json.dumps(outline)), lambda name: data).data)
        result.files.append(deck_path.name)
    report += _pictures(template_path, deck_path, folder, result, built_labels)
    final = (
        "TEMPLATE PROBE REPORT\n"
        + ("(the words of the template's slides are hidden)\n" if hide_text else "")
        + "\n"
    )
    final += (
        (_hide(report) if hide_text else report)
        + "\n\nThings to look at:\n"
        + ("\n".join(f"- {i}" for i in result.issues) or "- nothing found")
    )
    (folder / "report.txt").write_text(final, encoding="utf-8")
    (folder / "probe.json").write_text(
        json.dumps(
            {
                "template": template_path.name,
                "issues": result.issues,
                "slides_built": result.slides_built,
                "slides_failed": result.slides_failed,
                "samples": [
                    {
                        "number": s.number,
                        "kind": s.kind,
                        "layout": s.layout,
                        "items": len(s.items),
                        "slots": len(s.slots),
                    }
                    for s in samples
                ],
                "layouts": [{"name": lay.name, "kind": lay.role} for lay in info.layouts],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    result.files += ["report.txt", "probe.json"]
    return result


def _pictures(
    template_path: Path, deck_path: Path, folder: Path, result: ProbeResult, labels: list[str]
) -> str:
    """PowerPoint pictures and contact sheets of the template and the probe deck, and its overflow measurements; skipped without PowerPoint."""
    from forge.slides import preview
    from forge.slides.contact_sheet import ContactSheetUnavailable, make_contact_sheets
    from forge.slides.measure import measure_deck, overflow_problems

    text = ""
    try:
        for name, source in (("template", template_path), ("probe-deck", deck_path)):
            if not source.exists():
                continue
            pictures = preview.export_slides(source, folder / f"{name}-pictures")
            result.files.append(f"{name}-pictures/ ({len(pictures)} slides)")
            try:
                sheets = make_contact_sheets(pictures, folder)
                for sheet in sheets:
                    target = folder / f"{name}-{sheet.name}"
                    sheet.replace(target)
                    result.files.append(target.name)
            except (ContactSheetUnavailable, OSError):
                pass
        if deck_path.exists():
            spilled = overflow_problems(measure_deck(deck_path))
            normal: list[str] = []
            stress: list[str] = []
            for line in spilled:
                match = re.match(r"slide (\d+)", line)
                label = labels[int(match[1]) - 1] if match and int(match[1]) <= len(labels) else ""
                (stress if "long text" in label else normal).append(f"{line}  [{label}]")
            text += "\n\nPowerPoint measured text that does not fit with NORMAL text (a real problem):\n" + (
                "\n".join(f"- {s}" for s in normal) if normal else "- none"
            )
            text += (
                "\n\nWith deliberately LONG text (expected where boxes are tight; shows how the template copes):\n"
                + ("\n".join(f"- {s}" for s in stress) if stress else "- none")
            )
            result.issues += [f"overflow with normal text: {s}" for s in normal]
            if stress:
                result.issues.append(
                    f"{len(stress)} text boxes overflow with deliberately long text (see the report): content for those slides must be kept short"
                )
    except (preview.PreviewUnavailable, OSError, ValueError, KeyError) as error:
        text += f"\n\nNo pictures or measurements could be made: {error}"
        result.issues.append(f"no pictures: {error}")
    return text
