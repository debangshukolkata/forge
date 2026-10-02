# vision

Vision tooling: image/PDF utilities, eval sets and metrics, the labelling helper.

- **Depends on:** safety, toolkit
- **Invariants:** Eval labels and samples stay local.
- **Tests:** test_live_vision.py, test_vision.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
