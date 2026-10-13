"""Rebuild the outlines found in a deck-benchmark run with the current code and count the text PowerPoint measures as not fitting.

    python scripts/dev/overflow_check.py C:\\Work\\ForgeRuns\\deckbench\baseline-3 [--tasks d03_training,d17_marketing_plan]

A quick way to see whether a change to the layouts or the fitting estimate removes overflow, without running the model again."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from forge.slides.build import build_deck
from forge.slides.measure import measure_deck, overflow_problems
from forge.slides.spec import parse_deck


def find_outline(workspace: Path) -> Path | None:
    for path in sorted((workspace / "project").rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and "slides" in data and "title" in data:
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--tasks", default="")
    args = parser.parse_args()
    wanted = {t for t in args.tasks.split(",") if t}
    total = 0
    for workspace in sorted(
        p for p in args.run.iterdir() if p.is_dir() and p.name.startswith("d") and "_" in p.name
    ):
        if "_pictures" in workspace.name or (wanted and workspace.name not in wanted):
            continue
        outline = find_outline(workspace)
        if outline is None:
            continue
        project = outline.parent

        def read_image(name: str, project: Path = project) -> bytes:
            return next(project.rglob(Path(name).name)).read_bytes()

        try:
            built = build_deck(parse_deck(outline.read_text(encoding="utf-8")), read_image)
        except Exception as error:  # a template or picture the run had; skip it
            print(f"{workspace.name}: not rebuilt ({str(error)[:80]})")
            continue
        with tempfile.TemporaryDirectory() as folder:
            deck = Path(folder) / "deck.pptx"
            deck.write_bytes(built.data)
            problems = overflow_problems(measure_deck(deck))
        total += len(problems)
        print(f"{workspace.name}: {len(problems)} overflow(s)")
        for line in problems[:6]:
            print("   ", line.encode("ascii", "replace").decode()[:200])
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
