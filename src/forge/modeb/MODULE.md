# modeb

Mode B: host profiles, assumptions register, pinned contracts, standalone workspace and output.

- **Depends on:** config, kb, safety, verify, workspace
- **Invariants:** In Mode B Forge never reads outside the workspace and the profile folder (safety invariant 2).
- **Tests:** test_contracts.py, test_frontend_setup.py, test_learning.py, test_live_modeb.py, test_modeb.py, test_modeb_profile.py, test_web.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
