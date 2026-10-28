"""Name the reference pictures that already exist in each asset's front matter (TODO L0, D-510).

    python scripts/dev/link_previews.py

`find_asset` and `add_asset` already find `assets/preview/<id>-*.jpg` by name, but the catalogue build warns "no preview yet" until the asset's
front matter has a `preview:` line. For each asset of a visual type without one, this adds the line using `<id>-desktop.jpg`, else
`<id>-specimen.jpg`, else `<id>.jpg`, if that picture exists. It changes nothing else. Then run `python scripts/build_asset_catalogue.py`."""

from __future__ import annotations

import re
from pathlib import Path

from forge.parity.assets import PREVIEW_TYPES

SKILLS = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills"
FRONT = re.compile(r"\A(---\s*\n)(.*?)(\n---\s*\n)", re.S)


def link(skill: Path) -> int:
    count = 0
    for path in sorted((skill / "assets").glob("*/*.md")):
        match = FRONT.match(path.read_text(encoding="utf-8"))
        if match is None or re.search(r"^preview:", match.group(2), re.M):
            continue
        if not re.search(rf"^type:\s*({'|'.join(PREVIEW_TYPES)})\s*$", match.group(2), re.M):
            continue
        # A React version of a screen or layout shows the picture of the plain version it was made from.
        for stem, suffix in [(path.stem, s) for s in ("-desktop.jpg", "-specimen.jpg", ".jpg")] + [
            (path.stem.replace("-react", "", 1), "-desktop.jpg")
        ]:
            picture = skill / "assets" / "preview" / f"{stem}{suffix}"
            if picture.is_file():
                text = path.read_text(encoding="utf-8")
                path.write_text(
                    text[: match.end(2)] + f"\npreview: assets/preview/{picture.name}" + text[match.end(2) :],
                    encoding="utf-8",
                    newline="\n",
                )
                count += 1
                break
    return count


if __name__ == "__main__":
    for folder in sorted(SKILLS.glob("*/assets")):
        print(f"{folder.parent.name}: {link(folder.parent)} previews linked")
