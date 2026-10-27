# parity

Claude Code parity features: skills (incl. `skill_install.py`: `forge skill add` from a GitHub link or folder, D-207), custom agents, FORGE.md instructions, MCP client, @-mentions, local history, sessions.

- **Depends on:** config, errors, llm, protocol, safety, toolkit, workspace
- **Invariants:** MCP server tools join the agent through the registry; their output is untrusted (injection markers apply).
- **Tests:** test_parity.py, test_web.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **MCP allow-list (D-499):** a configured server starts only when the user's settings.json `mcp_allow` lists it for this project (`safety/mcp_allow.py`); unlisted servers and tools are reported in `McpHub.errors` / `hidden` and the `mcp` notice, never exposed. All MCP output is labelled untrusted and redacted. Mode B adds: a warning notice per server, a refusal when call arguments contain a host-identifying term, host terms masked in results, and an `mcp_call` notice per call (server, tool, redacted arguments). Permission gate unchanged (ask by default). Tests: test_mcp_allowlist.py.
- **Path-scoped rules (D-297):** `path_rules.py`: `rules/*.md` files with a `paths:` list load only when a matching file is read or edited (home `rules/`, the repository-level folder's `rules/`, `<workspace>/.forge/rules/`); delivered once per session with the tool result. Tests: test_path_rules.py.
- **Skill install (D-468):** `skill_install.py` downloads the repository zip (limit 150 MB) and unpacks only the requested folder or the folders holding a SKILL.md.
- **Plugins and hooks (D-501):** `plugins.py`: plugin folders in DebCraft Home (`plugin.json`, `commands/`, `agents/`, `skills/`, `hooks.json`), off until `forge plugin enable`, never read from a workspace, no MCP servers or permission rules from a plugin; the agent's hook runner is `agent/hooks.py`.
- **Skill A/B arms (C16):** `FORGE_DISABLED_SKILLS` switches skills off; `FORGE_EXTRA_SKILLS_DIR` (folders joined by the OS path separator) adds skill folders after the built-in ones and before the user's own, so `scripts/benchmark/run_skill_arms.py` can show the original Superpowers or mattpocock skills to an isolated benchmark home. Unset in normal use.
