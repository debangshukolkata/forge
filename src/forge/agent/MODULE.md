# agent

The main agent core: the loop (model call -> tool calls -> results -> repeat), no scripted failure handling (D-155). Knows nothing about requirements, reports or subagents.

- **Depends on:** context, errors, llm, protocol, safety, toolkit, tools, workspace
- **Invariants:** Every tool call gets a result, in order, even on interrupt. The loop owns every tool call
  (providers never execute tools). No phase machine (D-128..132). Tool results are capped and redacted here.
- **Tests:** test_agent_loop.py, test_events.py, test_tool_output.py
- A long tool result is also saved in full, redacted and capped, for the web UI to show on request (`tool_output.py`, D-195).
- **Decisions:** docs/DECISIONS.md (D-128..D-132 loop and cadence); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
