# environment

The per-machine environment: live connectivity checks (Azure, Postgres, Gemini, Tesseract, the system itself), the
model plan Forge proposes from them, and the saved result (`<home>/environment.json`). Shown by the web UI's
setup screen (D-186); the confirmed plan is applied to the router whenever a session starts.

- **Depends on:** config, doctor, errors, safety, vision
- **Invariants:** no secret value is ever stored or returned (details are redacted, only env var *names* appear); the saved file only
  holds check results and role -> model keys; a stale or unknown model key in it is ignored, never fatal.
- **Tests:** test_environment.py
- **Decisions:** docs/DECISIONS.md D-186.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
