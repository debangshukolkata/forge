# protocol

The UI-agnostic interface between engine and UIs: events (EventBus, JSONL log), user inputs, approvals.

- **Depends on:** safety
- **Invariants:** Payloads are redacted before they are stored or delivered. No print(). New event types must be ignorable by older UIs.
- **Tests:** test_agent_loop.py, test_db.py, test_events.py, test_frontend_smoke.py, test_kb.py, test_learning.py, test_live_agent.py, test_live_context.py (+17 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
