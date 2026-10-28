"""One-off: move the conditional sections of the ui-design-quality skill into files of their own (TODO L0 e, D-520).

    python scripts/dev/split_design_skill.py

SKILL.md was 58 KB (about 15,000 tokens every time it is loaded). The sections that matter only for one kind of job move to `recipes/skill-*.md`; SKILL.md keeps
the heading and a short pointer that says when to read the file (`load_skill` with `file`). The core process (sections 0 to 0h, 1 to 5, the gotchas) stays. Safe to
run once; it refuses when a section was already moved."""

from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "src" / "forge" / "skills" / "ui-design-quality"

# heading start -> (new file, pointer text that replaces the section body)
MOVES: dict[str, tuple[str, str]] = {
    "## 0i. ": (
        "skill-applications.md",
        "For an application (dashboard, table, form, settings, inbox, calendar, record page, board) do not write the screen from nothing: copy a complete screen "
        "and make it the product's own. `find_asset` with type `section` and the tag `app screen` lists them (for example `app-dashboard-kpi`; in a React project the "
        "`app-react-` version). Forge reads the brief for you: `design_candidates` says whether it is an application screen and you name `composition: app-...` "
        "(or `composition: custom <one line>`). **Before you build, call `load_skill` with name `ui-design-quality` and file `recipes/skill-applications.md`**: the "
        "families of screens, how to pick one, how to make it the product's own, how to reuse the shell and the phone rules.",
    ),
    "## 0j. ": (
        "skill-back-office.md",
        "For any tool people work in all day (approvals, queues, tables, records, settings, imports, reports) use the office polish look. **Call `load_skill` with "
        "name `ui-design-quality` and file `recipes/skill-back-office.md`** (and read `recipes/back-office-polish.md`, the ten rules and one recipe per component); "
        'start from the design system `ds-office-polish` (find_asset, type design-system, "office") unless the user supplied their own.',
    ),
    "## 6. ": (
        "skill-variants.md",
        "When the user asks for several designs, options or an A/B, call `build_variants` (each variant is built in its own folder with its own DESIGN.md and the "
        "results are shown side by side). **Call `load_skill` with name `ui-design-quality` and file `recipes/skill-variants.md` first** for the rules.",
    ),
    "## 7. ": (
        "skill-improving.md",
        "When the user says an existing UI looks bad or asks to restyle it, do not start by editing. **Call `load_skill` with name `ui-design-quality` and file "
        "`recipes/skill-improving.md`**: screenshot and audit it first, name what is wrong, change the tokens before the markup.",
    ),
    "## 8. ": (
        "skill-named-products.md",
        'When the user asks for the feel of a named product ("like Stripe", "like Linear"), **call `load_skill` with name `ui-design-quality` and file '
        "`recipes/skill-named-products.md`**: take the qualities, never the brand's own marks, fonts or copy.",
    ),
    "## 9. ": (
        "skill-motion.md",
        "Restraint wins: choose the effect budget from the MOTION_INTENSITY dial in DESIGN.md (hover and focus effects are free), one signature effect per page, "
        "everything off under `prefers-reduced-motion`. **For the budget table and the techniques, call `load_skill` with name `ui-design-quality` and file "
        "`recipes/skill-motion.md`**; the effects themselves are catalogue assets (`find_asset`, type effect).",
    ),
}


def main() -> None:
    path = SKILL / "SKILL.md"
    lines = path.read_text(encoding="utf-8").split("\n")
    starts = [i for i, line in enumerate(lines) if re.match(r"^## ", line)]
    out: list[str] = []
    cursor = 0
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        heading = lines[start]
        move = next((m for prefix, m in MOVES.items() if heading.startswith(prefix)), None)
        if move is None:
            continue
        name, pointer = move
        body = lines[start + 1 : end]
        if body and body[0].startswith("**Moved"):
            raise SystemExit(f"{heading!r} was already moved")
        target = SKILL / "recipes" / name
        target.write_text(
            heading.replace("## ", "# ", 1) + "\n" + "\n".join(body).rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        out.extend(lines[cursor : start + 1])
        out.append(pointer)
        out.append("")
        cursor = end
    out.extend(lines[cursor:])
    text = "\n".join(out)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"SKILL.md now {len(text):,} characters")


if __name__ == "__main__":
    main()
