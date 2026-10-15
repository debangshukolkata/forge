"""A blind gallery for the design taste test (TODO DIE8, docs/DESIGN_TASTE_TEST.md).

    python scripts/benchmark/blind_gallery.py <gallery-name> LABEL=run-name [LABEL=run-name ...]

For each brief that every run delivered, puts the desktop screenshots of the runs side by side under neutral names (Page 1, Page 2, ...) in a random order,
and writes the answer key to a separate file. Open gallery.html, choose the page you like most for each brief, write the choices down, and only then
open key.md. The audit counts and the model names are not in the gallery, so the choice is taste alone."""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import shutil
import sys
from pathlib import Path

RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "designbench"


def briefs_in_common(runs: dict[str, Path]) -> list[str]:
    sets = [
        {p.name.removesuffix("_shots") for p in folder.glob("*_shots") if (p / "desktop.png").is_file()}
        for folder in runs.values()
    ]
    return sorted(set.intersection(*sets)) if sets else []


def build(name: str, runs: dict[str, Path], out: Path, seed: int = 0) -> tuple[Path, Path]:
    """Writes out/gallery.html and out/key.md; returns both paths. The order is random but fixed by the seed, so a rebuild keeps the same page numbers."""
    out.mkdir(parents=True, exist_ok=True)
    random_order = random.Random(seed)
    sections: list[str] = []
    key: list[str] = [
        f"# Answer key for gallery {name}",
        "",
        "Open this only after you have written down your choices.",
        "",
    ]
    for brief in briefs_in_common(runs):
        labels = list(runs)
        random_order.shuffle(labels)
        cards: list[str] = []
        key.append(f"## {brief}")
        for position, label in enumerate(labels, start=1):
            source = runs[label] / f"{brief}_shots"
            for kind in ("desktop", "phone"):
                shutil.copyfile(source / f"{kind}.png", out / f"{brief}_{position}_{kind}.png")
            cards.append(
                f'<figure><figcaption>Page {position}</figcaption><a href="{brief}_{position}_desktop.png"><img src="{brief}_{position}_desktop.png" alt="Page {position}, desktop"></a>'
                f'<img class="phone" src="{brief}_{position}_phone.png" alt="Page {position}, phone"></figure>'
            )
            key.append(f"- Page {position}: {label} ({runs[label].name})")
        key.append("")
        sections.append(
            f'<section><h2>{html.escape(brief)}</h2><div class="row">{"".join(cards)}</div></section>'
        )
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Design taste test</title><style>'
        "body{font-family:system-ui,sans-serif;margin:24px;background:#fafafa;color:#111}h2{margin:32px 0 8px}"
        ".row{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}figure{margin:0;flex:1 1 420px}"
        "figcaption{font-weight:600;margin-bottom:6px}figure img{width:100%;border:1px solid #ccc}figure img.phone{width:160px;margin-top:8px}"
        "</style></head><body><h1>Design taste test</h1><p>For each brief, pick the page you like most. Write your choices down before opening key.md.</p>"
        + "".join(sections)
        + "</body></html>"
    )
    gallery = out / "gallery.html"
    gallery.write_text(page, encoding="utf-8")
    key_file = out / "key.md"
    key_file.write_text(chr(10).join(key), encoding="utf-8")
    (out / "key.json").write_text(
        json.dumps({"seed": seed, "runs": {k: str(v) for k, v in runs.items()}}), encoding="utf-8"
    )
    return gallery, key_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument(
        "runs", nargs="+", help="LABEL=run-name pairs, for example A=ab-gpt B=ab-argon-design"
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    runs: dict[str, Path] = {}
    for pair in args.runs:
        label, _, run = pair.partition("=")
        if not run or not (RUNS / run).is_dir():
            print(f"No run folder for {pair!r} under {RUNS}", file=sys.stderr)
            return 1
        runs[label] = RUNS / run
    gallery, key = build(args.name, runs, RUNS / f"gallery-{args.name}", args.seed)
    print(f"Open {gallery}; the key is {key} (open it last).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
