# slides

Presentation making (D-240, reading and editing D-241): an outline (`spec.py`, JSON or YAML) becomes a real, editable .pptx (`build.py`, python-pptx, optional extra
`forge[slides]`) with themes (`themes.py`) and text sized to its box (`fit.py`); `preview.py` has PowerPoint itself export a picture of each
slide (Windows with PowerPoint only) so the model can look at its work. The tools are in `tools/presentation.py`; the skill that teaches how
to write a good deck is `skills/make-presentation/SKILL.md`.

- **Depends on:** errors, toolkit
- **Invariants:** python-pptx is imported lazily (a missing library is a clear message, never a crash); PowerPoint gets its paths through environment variables, never through the command text, and never sees Forge's own variables (D-202); a user's open PowerPoint is not closed.
- **Tests:** test_slides.py, test_slides_edit.py, test_slides_freeform.py
- **Decisions:** docs/DECISIONS.md (D-240); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
