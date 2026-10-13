"""A quick look at a large company template: a short summary, a palettes picture and a few contact sheets (TODO P2.23, D-331).

    .venv\\Scripts\\python scripts\\dev\template_look.py "C:\\path\to\\company-template.potx" [--out folder]

Writes summary.txt, palettes.png, layouts-N.png (one slide per layout), samples-N.png (the template's own slides) and
template-look.zip with all of them next to the template (or into --out). Prints the summary and the file list. Needs PowerPoint for the
layout and sample pictures. Nothing is sent anywhere: look at the pictures before you send them.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from forge.errors import ForgeError  # noqa: E402
from forge.slides.look import run_look  # noqa: E402

PRINTED_MASTERS = 4  # more masters are in summary.txt


def short(summary: str) -> str:
    lines, masters = [], 0
    for line in summary.splitlines():
        if line.startswith("master "):
            masters += 1
        if line.startswith("layout pictures"):
            line = line[:400] + (" ... (all numbers in summary.txt)" if len(line) > 400 else "")
        if masters <= PRINTED_MASTERS or not (line.startswith("master ") or line.startswith("  colours")):
            lines.append(line)
    if masters > PRINTED_MASTERS:
        lines.insert(
            1, f"({masters} masters: the first {PRINTED_MASTERS} are shown here, all are in summary.txt)"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("template", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    logging.getLogger("dotenv").setLevel(logging.ERROR)
    if not args.template.is_file():
        print(f"No file at {args.template}")
        return 2
    folder = args.out or args.template.with_name(args.template.stem + "-look")
    try:
        look = run_look(args.template, folder)
    except ForgeError as error:
        print(f"The template could not be read: {error}")
        return 1
    print(short(look.summary))
    for note in look.notes:
        print("NOTE:", note)
    print(f"\nFiles in {folder}:")
    for name in look.files:
        print(" -", name)
    print(
        "Send template-look.zip, or photograph summary.txt, palettes.png and the first layouts and samples pictures."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
