# agent

The main agent core: the loop (model call -> tool calls -> results -> repeat), no scripted failure handling (D-155). Knows nothing about requirements, reports or subagents.

- **Depends on:** config, context, errors, llm, parity, protocol, safety, toolkit, tools, workspace
- **Invariants:** Every tool call gets a result, in order, even on interrupt. The loop owns every tool call
  (providers never execute tools). No phase machine (D-128..132). Tool results are capped and redacted here.
- **Tests:** test_agent_loop.py, test_events.py, test_tool_output.py
- A long tool result is also saved in full, redacted and capped, for the web UI to show on request (`tool_output.py`, D-195).
- **Decisions:** docs/DECISIONS.md (D-128..D-132 loop and cadence); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Hooks (D-501):** `hooks.py`: `pre_tool` (deny only), `post_tool`, `session_start`, `session_end`, `user_message` hooks run through the permission gate; a hook the gate would ask about is skipped, a hook cannot approve anything.
- **Request hints (D-518, D-527):** with each new user request the loop adds the catalogue matches (`tools/assets.py`) and, for a request for several designs of one page, a note to build them with `build_variants` (`hints.py`); plain pattern matching, nothing leaves the machine.
- **Repeated calls (HW1, D-578; HW5, D-580):** `repeats.py` (`RepeatLedger`: per call, the step, the result's digest and the id of its whole result). The loop answers an identical read, search or listing whose first result is still whole in the history with a pointer, and adds a note from the third identical answer on; the event carries `repeat_of`. A fact in the result, no refusal (D-155 stands). At the end of a turn the loop asks once for an API call made before the last code change to be made again after it (HW5, `proof_call` notice).
- **Notes in tool results (D-600, D-601):** `hints.py` `read_only_database_note` (a refused database write: use the scratch tools, do not patch the application) and `name_resolution_note` (a host that does not resolve: usually the VPN or DNS); `loop.py` adds them to the result of a running or calling tool, at most twice each per session, and asks once at the end of a turn for the proof through the API when the running-system skill was loaded, code changed and no API call followed.
