# diagnose

forge diagnose: integrity check of delivered code, fresh-copy run, read-only analysis subagent, report.

- **Depends on:** db, llm, safety, subagents, toolkit, tools, verify, workspace
- **Invariants:** Read-only on the user's real repository.
- **Tests:** test_diagnose.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
