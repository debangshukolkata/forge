"""Append a dated gotcha to a DebCraft skill (TODO C13): what went wrong in a real run, so the next run avoids it.

    python scripts/dev/add_gotcha.py <skill> "what to watch for" [--task t05_inventory_feature]

The text is added under the skill's `## Gotchas` heading (created when missing) as `- (YYYY-MM-DD, task) text`."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills"


def add_gotcha(skill: str, text: str, task: str = "") -> Path:
    path = SKILLS / skill / "SKILL.md"
    if not path.is_file():
        raise SystemExit(
            f"No skill {skill!r}. Skills: {', '.join(sorted(p.parent.name for p in SKILLS.glob('*/SKILL.md')))}"
        )
    content = path.read_text(encoding="utf-8").rstrip("\n")
    if "## Gotchas" not in content:
        content += "\n\n## Gotchas"
    origin = f"{date.today():%Y-%m-%d}" + (f", {task}" if task else "")
    path.write_text(content + f"\n- ({origin}) {' '.join(text.split())}\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill")
    parser.add_argument("text")
    parser.add_argument("--task", default="")
    args = parser.parse_args()
    print(f"Added to {add_gotcha(args.skill, args.text, args.task)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
