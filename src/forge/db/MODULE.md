# db

Database access: access levels, scratch schema, introspection, DB requests, table checks.

- **Depends on:** config, safety, workspace
- **Invariants:** DB writes only happen in the scratch schema for the current requirement (safety invariant 4).
- **Tests:** test_db.py, test_live_db.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Running a copy of the application on its own data (D-568):** `copy_rows.py` (`copy_table`: a table's columns, primary key and rows from a database DebCraft may only read into the scratch schema, with COPY from one connection to the other so rows never pass through the model; credential tables refused; a `where` filter checked as one read-only statement; source-only types become text; serial and identity columns keep counting) and `session.py` (`set_app_variables` / `command_environment`: the application's own database setting names mapped to parts of the scratch connection, names stored in `.forge/db_app_env.json`, values only in the command environment). Tests: test_db_copy.py (local Postgres).
