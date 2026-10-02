# workflow

The requirement workflow around the main agent: the orchestrator (a flat loop with optional plan and
requirements records, change requests, export), persistent state (`state.json`: tasks, cadence, exported),
final reports, the learning hooks (related past requirements, lessons, the background retro) and the frontend
smoke check.

- **Depends on:** agent, config, kb, learning, llm, modeb, parity, protocol, subagents, toolkit, tools, verify, workspace
- **Invariants:** No phase machine and no turn-blocking approvals (D-128..132, D-153). The retro runs in the
  background and never gates the user's next message. Resume is automatic and silent; `state.exported` is the
  resume-safety signal. Known debt: `orchestrator.py` type-references `engine.SessionHost`.
- **Tests:** test_orchestrator.py, test_frontend_smoke.py, test_learning.py, test_live_orchestrator.py
- **Decisions:** docs/DECISIONS.md (D-128..D-133 workflow, D-153 approvals); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
