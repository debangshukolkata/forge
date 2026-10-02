# safety

Write jail, permission gate, shell classifier, low-integrity sandbox, secret redaction, SQL guard, injection markers, localhost server security.

- **Depends on:** errors
- **Invariants:** Safety invariants 1-5 live here. Imports nothing from Forge except errors. Every change needs a test.
- **Tests:** test_agent_loop.py, test_config.py, test_db.py, test_events.py, test_frontend_smoke.py, test_hardening.py, test_kb.py, test_learning.py (+20 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
