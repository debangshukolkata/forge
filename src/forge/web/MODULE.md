# web

The local web UI server (FastAPI) and the React build in web/react/. Route modules: `auth_routes` (login, password change),
`environment_routes` (setup guide data, per-check tests, optional-tool answers, the model plan), `contracts_routes`
(Mode B contracts), `tool_output_routes` (full tool output), `project_list` and `project_memory` (the open-a-project list), `deps_routes` (the Dependencies section, D-238).

- **Depends on:** agent, config, deps, doctor, engine, environment, memory, errors, modeb, parity, protocol, safety, session, tools, workspace
- **Invariants:** 127.0.0.1 only, per-run session token, plus a local login (D-184: `accounts.py`, `auth_routes.py`; everything but the page shell and `/api/auth/*` needs a signed-in session). No endpoint writes the `.env` file or returns a key (D-204). State is derived from events so a reopened project looks the same as a live one.
- **Tests:** test_live_web_e2e.py, test_live_web_react.py, test_web.py, test_web_e2e.py, test_web_accounts.py, test_web_login_e2e.py,
  test_web_runmap_e2e.py, test_web_contracts.py, test_web_contracts_e2e.py, test_web_tool_output.py, test_setup_guide.py,
  test_web_setup_guide_e2e.py, test_project_memory.py, test_deps.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
