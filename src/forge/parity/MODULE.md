# parity

Claude Code parity features: skills, custom agents, FORGE.md instructions, MCP client, @-mentions, local history, sessions.

- **Depends on:** config, errors, llm, protocol, safety, toolkit, workspace
- **Invariants:** MCP server tools join the agent through the registry; their output is untrusted (injection markers apply).
- **Tests:** test_parity.py, test_web.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
