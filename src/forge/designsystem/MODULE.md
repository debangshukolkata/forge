# designsystem

DESIGN.md files (TODO DS1, D-348): the project's design system as YAML tokens (colors, typography, rounded, spacing, components, with `{colors.primary}`
references) plus ordered prose sections, in the open DESIGN.md format by Google Labs (Apache-2.0; this is our own implementation of the published format,
no code copied). `spec.py` parses a file into a model and resolves references; `lint.py` finds structural, reference and contrast problems and a few
look problems (one-hue palette, too many accents); `export.py` writes the tokens as Tailwind v4 `@theme` CSS, CSS variables, W3C design tokens or Tailwind v3
JSON; `blueprint.py` notes missing blueprint parts (page composition, imagery, motion, responsive, accessibility) and decisions with no stated reason (DIE2); `diff.py` compares two files; `concept.py` checks the Concept section (idea and signature visual) a brand page starts from (D-486). `brief_kind.py` tells an application brief from a brand-page brief in plain words (D-488). Extensions are tolerated, not required: our dials and do's headings, `website`, Known Gaps, Responsive Behavior, font substitutes, component variants as separate entries.
The tools are in `tools/design_md.py`; the skill is `skills/ui-design-quality/SKILL.md` (sections 0c and 0d).

- **Depends on:** brand, errors
- **Invariants:** a file is data: nothing in it is executed or fetched; unknown keys and headings are kept, never an error; a colour pair that fails 4.5:1 contrast is an error, never silently exported as fine; the front matter must be valid YAML between `---` lines.
- **Tests:** test_designsystem.py
- **Decisions:** docs/DECISIONS.md (D-348); the format specification is public (github.com/google-labs-code/design.md).

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
