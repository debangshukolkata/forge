# workspace

The per-requirement workspace: copy, baseline manifest, the single write gate (jail + checkpoint), output/ builder, checkpoints, Python/Node environment detection, read grants (`read_grants.py`: read-only places the user opened, D-208).

- **Depends on:** errors, safety
- **Invariants:** Every write goes through Workspace (safety invariant 1). Preserve BOM and line endings.
Changed expectations in the user's existing tests are recorded for the delivery report (`test_expectations.py`, D-560).

- **Tests:** test_agent_loop.py, test_context.py, test_contracts.py, test_db.py, test_diagnose.py, test_frontend_setup.py (and others; see tests/)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Attachments (D-469):** `Workspace.input_path` resolves `.forge/inputs/...` and `.forge/tool_outputs/...` for reading only; `read_file` and `list_dir` use it.
