# web

The local web UI server (FastAPI) and the React build in web/react/.

- **Depends on:** config, doctor, engine, errors, modeb, parity, protocol, safety, session, tools, workspace
- **Invariants:** 127.0.0.1 only, per-run session token. State is derived from events so a reopened project looks the same as a live one.
- **Tests:** test_live_web_e2e.py, test_live_web_react.py, test_web.py, test_web_e2e.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
