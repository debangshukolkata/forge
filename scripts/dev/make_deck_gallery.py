"""The examples gallery for presentations (TODO P3.5): one contact sheet and the original request per benchmark task.

    python scripts/dev/make_deck_gallery.py C:\\Work\\ForgeRuns\\deckbench\\baseline-3 d02_investor_pitch d04_data_story ...

Reads a deck-benchmark run folder (`<task>_prompt.txt`, `<task>_pictures/slide-N.png`, `results.json`), writes
`docs/gallery/<task>.jpg` (a contact sheet of all slides, shrunk) and `docs/GALLERY.md` (request, slide count, the judge's scores).
The pictures are PowerPoint's own renderings, made during the benchmark."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from forge.slides.contact_sheet import make_contact_sheets  # noqa: E402

GALLERY = REPO / "docs" / "gallery"
DEFAULT_TASKS = (
    "d02_investor_pitch",
    "d04_data_story",
    "d11_product_launch",
    "d15_incident_postmortem",
    "d19_research_summary",
    "d20_onboarding",
)
SHEET_WIDTH = 1500
QUALITY = 80


def _slide_number(path: Path) -> int:
    match = re.search(r"slide-(\d+)", path.name)
    return int(match.group(1)) if match else 0


def build_sheet(run: Path, task: str) -> Path | None:
    from PIL import Image

    pictures = sorted((run / f"{task}_pictures").glob("slide-*.png"), key=_slide_number)
    if not pictures:
        return None
    scratch = GALLERY / f"_{task}"
    scratch.mkdir(parents=True, exist_ok=True)
    sheets = make_contact_sheets(
        pictures[:24], scratch
    )  # a gallery needs the feel of the deck, not all 60 slides
    target = GALLERY / f"{task}.jpg"
    with Image.open(sheets[0]) as sheet:
        picture = sheet.convert("RGB")
        picture.thumbnail((SHEET_WIDTH, SHEET_WIDTH * 2))
        picture.save(target, "JPEG", quality=QUALITY, optimize=True)
    for file in scratch.iterdir():
        file.unlink()
    scratch.rmdir()
    return target


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    run = Path(argv[0])
    tasks = argv[1:] or list(DEFAULT_TASKS)
    results_file = run / "results.json"
    results = (
        {row["id"]: row for row in json.loads(results_file.read_text(encoding="utf-8"))}
        if results_file.exists()
        else {}
    )
    GALLERY.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Examples gallery",
        "",
        f"Decks DebCraft made from the request shown, as rendered by PowerPoint (benchmark run `{run.name}`; made by `scripts/dev/make_deck_gallery.py`).",
        "Each picture is a contact sheet of the slides. The scores are the benchmark judge's (1 to 5, generous: 4 is a competent deck).",
        "",
    ]
    for task in tasks:
        sheet = build_sheet(run, task)
        prompt_file = run / f"{task}_prompt.txt"
        if sheet is None or not prompt_file.exists():
            print(f"{task}: nothing to show")
            continue
        request = prompt_file.read_text(encoding="utf-8").split("Save the finished presentation")[0].strip()
        row = results.get(task, {})
        lines += [
            f"## {task.split('_', 1)[1].replace('_', ' ').capitalize()}",
            "",
            "**The request**",
            "",
            "> " + request.replace("\n", "\n> "),
            "",
        ]
        if row:
            judge = row.get("judge") or {}
            scores = [
                judge[k]
                for k in ("story", "hierarchy", "contrast", "alignment", "polish", "fit")
                if k in judge
            ]
            average = f"{sum(scores) / len(scores):.1f}" if scores else "?"
            lines += [f"Slides: {row.get('auto', {}).get('slides', '?')}; judge average: {average}", ""]
        lines += [f"![{task}](gallery/{sheet.name})", ""]
        print(f"{task}: {sheet.relative_to(REPO)} {sheet.stat().st_size // 1024} KB")
    (REPO / "docs" / "GALLERY.md").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
