# tools

The tool implementations the agent can call (files, search, shell wrappers, KB, DB, web, browser, verify, vision, Mode B, learning) and the registry that lists them.

- **Web (D-209):** `web.py` (the tools and search providers), `web_chain.py` (fetch stages), `web_guard.py` (address policy),
  `web_extract.py` (HTML/PDF to text), `web_render.py` (read-only headless browser). A fetch never ends in nothing: see DECISIONS D-209.
- **Depends on:** config, db, doctor, environment, errors, llm, memory, modeb, parity, safety, toolkit, vision, workspace
- **Invariants:** Each tool has pydantic Args, a one-line summary() and a read_only flag. Errors become ToolResult(ok=False). Tools that start agents live in forge.agent, not here.
- **Tests:** test_context.py, test_contracts.py, test_db.py, test_frontend_setup.py, test_hardening.py, test_kb.py, test_learning.py, test_live_verify.py (+9 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
