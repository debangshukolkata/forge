# Forge modules (D-152)

One Python package, `src/forge/`, split into modules with a strict one-way layering. A module may import only
from an **earlier tier**; `tests/test_module_boundaries.py` fails CI on an upward or same-tier import and on a
`MODULE.md` whose `Depends on:` line does not match the real imports. Each module folder has a `MODULE.md`
(purpose, dependencies, invariants, tests). **Read the `MODULE.md` of the module you are changing, not the whole
spec.** Single-file modules (`errors.py`, `net.py`, `session.py`, `cli.py`) are described here only.

| Tier | Modules | Role |
|---|---|---|
| 0 | errors, net | exceptions, TLS |
| 1 | safety | write jail, permissions, sandbox, redaction (safety invariants) |
| 2 | config, protocol, workspace | settings; events/inputs/approvals; the workspace write gate |
| 3 | llm, memory | providers, router, tokens, cost; auto-memory (user + project scope) |
| 4 | context, kb, toolkit | context window; knowledge base; tool contract + shell runners |
| 5 | db, parity, vision | database; skills/agents/MCP; vision |
| 6 | doctor | setup checks |
| 7 | modeb | host profiles, contracts |
| 8 | tools | tool implementations + registry |
| 9 | agent | the main agent loop (knows nothing about requirements or subagents) |
| 10 | subagents | explore / reviewer / debugger / custom agents, the `spawn_subagent` tool |
| 11 | workflow | orchestrator, persistent state, reports, learning hooks |
| 12 | diagnose | forge diagnose |
| 13 | engine | session host, slash commands (composition root) |
| 14 | session, ui | session factory, terminal client |
| 15 | web | web server + React build |
| 16 | cli | command line |

## Status of modules affected by the revamp (D-156)
`kb` (repo index) is being retired (`learning` is gone: D-158, `verify` is gone: D-159); the replacements are FORGE.md files and the auto-memory folder (`parity`, `memory`) and the shell tool
(`toolkit`). Until a module's removal is ticked in TODO.md it still exists and is still tested.

## Rules
1. Import only from earlier tiers. Need something from a later tier? Move the shared piece down, or pass it in
   (a callable or Protocol) from the composition root (`engine`).
2. Update `Depends on:` in `MODULE.md` when you add an import (the test tells you).
3. Imports under `if TYPE_CHECKING` are ignored by the test but are still debt: currently
   `workflow/orchestrator.py` type-references `engine.SessionHost`.
4. Not yet enforced (future): importing only a module's public names rather than its internals.
5. Running only one module's tests: `pytest tests/test_<module>*.py` (see each MODULE.md `Tests:` line), plus
   `tests/test_module_boundaries.py`.

## What moved in D-152
`tools/{base,shell,powershell,background}` -> `toolkit/`; `engine/{events,approvals,inputs}` -> `protocol/`;
`db/checks` -> `workspace/server_checks`; `web/security` -> `safety/server_security`;
`modeb/workspace.ensure_shared_stub_packages` -> `workspace/stub_packages`; the `spawn_subagent` tool
`tools/parity` -> `subagents/spawn_tool` (subagents therefore no longer get it, so they cannot nest).
Second split: `agent` -> `agent` (loop) + `subagents` (subagent, review, spawn_tool) + `workflow` (orchestrator,
state, reports, learning_hooks, frontend_smoke). D-155 then removed the stuck detector and the escalation ladder
altogether, so the loop has no failure-handling policy of its own.
