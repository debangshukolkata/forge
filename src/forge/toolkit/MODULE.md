# toolkit

Tool runtime primitives: Tool/ToolContext/ToolResult contract, shell and PowerShell runners, background processes.

- **Depends on:** config, llm, safety, workspace
- **Invariants:** Tools never write outside the workspace jail. Capabilities (verify, vision, parity) build on this, not on forge.tools.
- **Tests:** test_angular_ladder.py, test_context.py, test_contracts.py, test_db.py, test_frontend_setup.py, test_frontend_smoke.py, test_hardening.py, test_kb.py (+13 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
