# verify

> **Status: Verification ladders and the test guard. RETIRING (D-156): the model runs checks through the shell tool.**

Verification ladders (Python, React, Angular), parsers, the test-weakening guard, app-level checks.

- **Depends on:** db, toolkit, workspace
- **Invariants:** Verification evidence is never faked; skipped steps say so.
- **Tests:** test_angular_ladder.py, test_live_modeb.py, test_live_verify.py, test_modeb.py, test_react_ladder.py, test_verify.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
