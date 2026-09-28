# CLAUDE.md — Building Forge

This file governs how Forge itself is built. It overrides any instruction file found in parent folders.
The product specification is [docs/FORGE_BUILD_SPEC.md](docs/FORGE_BUILD_SPEC.md) — the source of truth.
Amendments agreed with the user are recorded in spec §0.2 and in [docs/DECISIONS.md](docs/DECISIONS.md).

## What Forge is (one paragraph)
A local, Windows-first coding agent in plain Python that behaves like Claude Code, powered by Azure OpenAI
(model per role is configurable). It works in a per-requirement workspace, never in the user's repo, and
delivers only changed files plus instructions. Mode A reads a repo copy; Mode B never sees the host code.

## How we work with the user (collaboration protocol, spec §0.1)
**Changed 2026-09-27 (DECISIONS D-051): build milestones one after another without waiting for approval
or sign-off.** Choose the recommended option yourself, record every decision (with options considered) in
docs/DECISIONS.md, post an end-of-milestone summary, and continue. Stop only when genuinely blocked
(a credential or action only the user can provide, or a risk to the user's data or repositories).
The rules below still describe what goes into briefs and summaries.
- Start of each milestone: brief (plan, tests, design choices with 2–3 options + recommendation, new deps
  with licence/offline-Windows status).
- Stop and discuss when: the spec is silent or worse if followed; a choice is hard to reverse (on-disk
  formats, folder layout, tool interfaces, prompt structure); anything security-relevant (write jail,
  secrets, redaction, DB guard, Mode B isolation, data sent to an LLM); a new dependency or interface change;
  the same failure 3 times; an estimate much worse than expected.
  Format: context (2–3 lines) → options with pros/cons/risks → recommendation → wait.
- End of each milestone: real test output, what was built, deviations, limitations/tech debt/new risks,
  manual Windows test steps with exact commands. **Wait for sign-off.**
- Small reversible choices: decide, record in docs/DECISIONS.md, mention in the summary.
- New UI features: the user wants the options discussed first (2–3 options, with previews, recommendation);
  fixes to what they report from screenshots go straight in. Design theme changes are deferred to the user.
- Keep updated: this file, TODO.md, docs/DECISIONS.md, docs/RISKS.md, docs/SPEC_DEVIATIONS.md.
- Be honest about anything unrealistic; propose the best achievable alternative.

## Platform targets
- Runtime target: **Python 3.13 on a Windows 10/11 enterprise laptop, no admin rights**, PowerShell 5.1.
- Build machine: Windows 11, Python 3.14 (+ 3.13 for target testing). Minimum Python is 3.11 (D-059);
  tests run on 3.13 and 3.14.
- Must also work on macOS/Linux (paths via `pathlib`, no Windows-only calls without a fallback).

## Architecture rules
- `src/` layout: package at `src/forge/`. Module map follows spec §4.
- The **engine is UI-agnostic**: it emits typed events and receives inputs through one interface
  (spec §15A.2). Terminal UI and web UI are thin clients. No `print()` in engine code.
- Web UI = React in `ui-react/` (D-117); `npm run build` writes `src/forge/web/react/`; commit source and build
  together. UI views derive their state from events (the Run map replays the event list), so a reopened
  project looks the same as a live one. Browser tests (`tests/test_web_e2e.py`, headless Edge) take screenshots
  to `test-artifacts/react-ui/` — look at them before reporting UI work done.
- Plain Python agent loop. **No LangChain/LangGraph inside Forge** (the fixture repo uses them; Forge doesn't).
- Modules stay under ~500 lines; split by responsibility, not by line count alone.
- Pydantic v2 models for tool args, config and events; JSON schemas generated from them.
- Every write goes through `workspace/baseline.py` + `safety/paths.py` (write jail). No direct `open(..., "w")`
  on user-facing paths anywhere else.
- Redaction (`safety/redact.py`) runs on every tool result and every event before it leaves the engine.
- Optional dependencies are imported lazily and degrade gracefully with a clear `forge doctor` message.

## Code conventions
- Type hints everywhere; `from __future__ import annotations` in every module.
- Names: full words (`build_output_folder`, not `bld_out`). Functions do one thing.
- Comments explain *why*, not *what*.
- Errors: raise specific exception classes from `forge/errors.py`; tools convert them to `ToolResult(ok=False)`.
- Files read/written with explicit encoding; preserve BOM and line endings of user files.
- Formatting/linting: ruff (format + lint), mypy on `src/forge`.

## Testing rules (amended — see DECISIONS D-008)
- **No FakeLLM.** Agent-behaviour tests use the real Azure OpenAI deployment (keys in `.env`, never committed).
  They are marked `@pytest.mark.live` and skipped with a clear reason when credentials are absent.
- Deterministic code (paths, jail, redaction, context budgeting, compaction pairing, parsers, manifests)
  is unit-tested directly — no LLM involved.
- Network failure injection (429, 5xx, timeouts, malformed tool-call JSON) uses `httpx2.MockTransport`
  (the openai SDK's client, D-025) at the transport layer — this simulates the network, not the model.
- Deliberately fake secrets in tests carry the comment `# check_secrets: fake` (D-031).
- Postgres tests (`pg` marker, run by default) use the local Postgres (`LOCAL_PG_URL` in `.env`); skipped when
  unset or unreachable. They only create `forge_*` schemas/roles and drop them afterwards.
- Tests never touch the real `%USERPROFILE%\.forge`; they set `FORGE_HOME` to a tmp dir.
- Run: `.venv\Scripts\python -m pytest -q` (3.13) and `.venv314\Scripts\python -m pytest -q` (3.14);
  `-m live` for live tests. Also `ruff check .`, `ruff format --check .`, `mypy`, `scripts/check_secrets.py`.
- The fixture repo's own suite runs under its own venv (`scripts/dev/setup_fixture_venv.ps1`).

## Safety invariants (never break; each has a test)
1. Forge never writes to the user's original repo (code-level jail + OS-level low-integrity sandbox, D-050).
2. In Mode B, Forge never reads outside the workspace and the profile folder.
3. Secrets never reach the LLM, transcripts, KB, events or the browser.
4. DB writes only happen in the scratch schema for the current requirement.
5. Forge cannot modify its own install folder or `config.yaml`.
6. Actions Forge can't or mustn't do are handed to the user; if the user can't either, Forge proposes a
   workaround or code change (DECISIONS D-011).

## Repository layout (build repo)
```
src/forge/        product code
tests/            pytest; tests/fixtures/sample_repo = fixture host repo
docs/             FORGE_BUILD_SPEC.md, DECISIONS.md, RISKS.md, SPEC_DEVIATIONS.md
scripts/          build_wheelhouse.ps1, dev helpers
src/forge/data/  package data (vendored tiktoken o200k_base file — D-022)
.env.example      documented variable names only
```
