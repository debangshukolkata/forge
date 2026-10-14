# brand

The brand kit documents share (TODO W4, D-347): colours and fonts of the user's company, in the same field names as the presentation brand kit
(`accent`, `background`, `text`, `muted`, `surface`, `accent_text`, `title_font`, `body_font`), so one JSON file can describe the brand for a deck, a Word
document, a workbook and a PDF. `kit.py` holds the model, the WCAG contrast maths and the derived colours (a heading colour that is readable on white,
text readable on the accent). The builders in `documents`, `sheets` and `pdfs` apply it; a colour pair that fails contrast is corrected, never used.

- **Depends on:** errors
- **Invariants:** a colour is six hex digits (a `#` is allowed); text colours derived from a brand always meet 4.5:1 contrast on their background; the kit only carries colours and font names, never files or addresses.
- **Tests:** test_brand.py
- **Decisions:** docs/DECISIONS.md (D-347). The presentation brand kit (`slides/spec.py`, D-281) keeps its own copy of the model for now.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
