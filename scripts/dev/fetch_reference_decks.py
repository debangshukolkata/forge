"""Collect real-world .pptx files for testing the presentation readers (TODO P2.24, D-399).

    python scripts/dev/fetch_reference_decks.py [target-folder]      (default C:\Work\ForgeSamples\reference-decks)

Shallow, sparse git clones of three open-licence repositories whose test data holds hundreds of real PowerPoint files, kept OUTSIDE this repository: Apache POI (Apache-2.0),
python-pptx (MIT) and LibreOffice core (MPL-2.0). See docs/REFERENCE_DECKS.md for what each is good for and why designed marketing templates are not collected."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SOURCES = (
    ("poi", "https://github.com/apache/poi.git", ["test-data/slideshow"]),
    (
        "python-pptx",
        "https://github.com/scanny/python-pptx.git",
        ["tests/test_files", "features/steps/test_files"],
    ),
    ("lo", "https://github.com/LibreOffice/core.git", ["sd/qa/unit/data/pptx", "oox/qa/unit/data"]),
)


def run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def main(argv: list[str]) -> int:
    target = Path(argv[0]) if argv else Path(r"C:\Work\ForgeSamples\reference-decks")
    source_folder = target / "_src"
    source_folder.mkdir(parents=True, exist_ok=True)
    for name, url, folders in SOURCES:
        clone = source_folder / name
        if not clone.exists():
            run(
                ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", url, name],
                cwd=source_folder,
            )
            run(["git", "sparse-checkout", "set", *folders], cwd=clone)
        count = sum(1 for p in clone.rglob("*") if p.suffix.lower() in (".pptx", ".potx", ".ppsx", ".pptm"))
        print(f"{name}: {count} files in {clone}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
