# environment

The per-machine environment: the settings-file guide (`guide.py`: where the `.env` is, which names, a template, what is
filled in, D-204), the connectivity checks (`checks.py`: the system, Azure, the DebCraft database, the read-only Development
database, Gemini (one real call per Gemini model after a yes, with the region; a failure carries `steps`, shown under an (i) icon), Node.js and npm (a real npm registry call after a yes, D-404), Tesseract; each run on request), the model plan DebCraft proposes from them (`plan.py`), and the saved result
(`store.py`, `<home>/environment.json`: results, the confirmed plan and the yes/no answers about the optional tools, D-201).
Shown by the web UI's Environment drawer (D-186); the confirmed plan is applied to the router whenever a session starts, and
`tesseract_ready` decides whether the `ocr_image` tool is offered (D-203).

A failed Tavily call writes `<home>/logs/tavily-<tool>-<time>.log` (`tavily_log.py`: request body, status, reply structure and text, never the token) and its error names the file (D-548).

- **Depends on:** config, doctor, errors, llm, net, safety, vision
- **Invariants:** no secret value is ever stored or returned (details are redacted, only env var *names* appear); the saved file only
  holds check results and role -> model keys; a stale or unknown model key in it is ignored, never fatal.
- **Tests:** test_environment.py, test_setup_guide.py, test_ocr.py, test_tavily_tool.py, test_tavily_kinds.py
- **Decisions:** docs/DECISIONS.md D-186, D-201, D-203, D-204, D-547, D-548.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
