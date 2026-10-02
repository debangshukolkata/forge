# llm

Provider-independent message/tool types, the Azure OpenAI adapter, router (role -> model, retries, fallback, cost), token counting, usage ledger.

- **Depends on:** config, errors, net, safety
- **Invariants:** Redaction runs before anything is sent. Providers implement the LLMProvider protocol; the agent loop owns every tool call.
- **Tests:** test_context.py, test_events.py, test_live_agent.py, test_live_context.py, test_live_db.py, test_live_kb.py, test_live_llm.py, test_live_verify.py (+6 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
