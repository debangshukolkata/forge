"""Run DebCraft's presentation readers over a folder of real-world .pptx/.potx files and list what breaks (TODO P2.24, D-399).

    python scripts/dev/reference_deck_sweep.py <folder> [--out report.md] [--limit N]

The folder is searched recursively. For each file the sweep opens it with python-pptx and runs `analyze_template`, `read_design`, `describe_design`, and the sample reader
the template builder uses; it records the exception type and message of any step that fails, and how long the file took. Nothing is written into the folder.
The sample decks are kept outside the repository (see docs/REFERENCE_DECKS.md for where they come from and their licences)."""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


def steps() -> list[tuple[str, object]]:
    from forge.slides import design_reader, template, template_samples

    reader = next(
        (
            getattr(template_samples, name)
            for name in ("read_samples", "analyze_samples", "find_samples")
            if hasattr(template_samples, name)
        ),
        None,
    )
    found: list[tuple[str, object]] = [
        ("analyze_template", lambda prs: template.describe_template(template.analyze_template(prs))),
        ("describe_design", lambda prs: design_reader.describe_design(design_reader.read_design(prs))),
    ]
    if reader is not None:
        found.append(("samples", reader))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--out", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    from pptx import Presentation

    files = sorted(
        p for p in Path(args.folder).rglob("*") if p.suffix.lower() in (".pptx", ".potx", ".ppsx", ".pptm")
    )
    if args.limit:
        files = files[: args.limit]
    pipeline = steps()
    failures: list[str] = []
    opened = 0
    slow: list[tuple[float, str]] = []
    for file in files:
        started = time.time()
        try:
            prs = Presentation(str(file))
        except Exception as error:
            failures.append(
                f"| {file.name} | open (python-pptx) | {type(error).__name__}: {str(error)[:100]} |"
            )
            continue
        opened += 1
        for name, step in pipeline:
            try:
                step(prs)  # type: ignore[operator]
            except Exception as error:
                last = traceback.extract_tb(error.__traceback__)[-1]
                failures.append(
                    f"| {file.name} | {name} | {type(error).__name__}: {str(error)[:100]} ({Path(last.filename).name}:{last.lineno}) |"
                )
        slow.append((time.time() - started, file.name))
    lines = [
        f"# Reference deck sweep: {len(files)} files, {opened} opened by python-pptx, {len(failures)} failures in our readers",
        "",
        "| file | step | error |",
        "|---|---|---|",
        *failures,
        "",
        "Slowest: " + ", ".join(f"{name} {seconds:.1f}s" for seconds, name in sorted(slow, reverse=True)[:5]),
    ]
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
