# db

Database access: access levels, scratch schema, introspection, DB requests, table checks.

- **Depends on:** config, safety, workspace
- **Invariants:** DB writes only happen in the scratch schema for the current requirement (safety invariant 4).
- **Tests:** test_db.py, test_live_db.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
