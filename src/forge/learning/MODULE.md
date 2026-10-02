# learning

> **Status: Library, lessons, retro, metrics, improvement proposals. RETIRING (D-156): replaced by FORGE.md files and auto-memory.**

Requirements library, lessons, metrics, self-improvement proposals, scope keys.

- **Depends on:** kb, llm, safety, workspace
- **Invariants:** Forge can never change its own installed code or prompts; it only proposes (spec 12.5).
- **Tests:** test_contracts.py, test_learning.py, test_live_learning.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
