# ui

Terminal client.

- **Depends on:** engine, llm, protocol
- **Invariants:** A thin consumer of events; all logic lives in the engine.
- **Tests:** test_m10_wiring.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
