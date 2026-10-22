# toolkit

Tool runtime primitives: Tool/ToolContext/ToolResult contract, shell and PowerShell runners, background processes, and
`app_keys` (the Azure model the user lets the app under test use, D-466), `private_env` (the names DebCraft itself uses are removed from the environment commands inherit, D-202).

- **Depends on:** config, errors, llm, net, safety, workspace
- **Invariants:** Tools never write outside the workspace jail. Capabilities (verify, vision, parity) build on this, not on forge.tools.
- **Tests:** test_context.py, test_contracts.py, test_db.py, test_frontend_setup.py, test_hardening.py (and others; see tests/)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
