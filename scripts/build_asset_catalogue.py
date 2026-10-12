"""Builds the asset catalogue of a skill folder: validates every asset and writes catalogue.json, INDEX.md and LICENSES.md.

    python scripts/build_asset_catalogue.py [skill folder]      (default: src/forge/skills/ui-design-quality)
    python scripts/build_asset_catalogue.py --check              fails if the committed files are out of date

Exit code 1 on any error (missing licence, missing file, wrong folder, duplicate id)."""

from __future__ import annotations

import sys
from pathlib import Path

from forge.parity.assets import ASSETS_FOLDER, build_catalogue, catalogue_files, write_catalogue

DEFAULT = Path(__file__).resolve().parents[1] / "src" / "forge" / "skills" / "ui-design-quality"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    folders = [Path(a) for a in argv if not a.startswith("--")] or [DEFAULT]
    status = 0
    for folder in folders:
        result = build_catalogue(folder)
        for problem in result.errors:
            print("ERROR", problem)
        if result.errors:
            status = 1
            continue
        if check:
            for name, text in catalogue_files(result).items():
                path = folder / ASSETS_FOLDER / name
                if not path.is_file() or path.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
                    print(f"OUT OF DATE {path}: run scripts/build_asset_catalogue.py")
                    status = 1
        else:
            write_catalogue(folder)
            print(
                f"{folder.name}: {len(result.assets)} assets, {len(result.warnings)} warnings (no preview yet)"
            )
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
