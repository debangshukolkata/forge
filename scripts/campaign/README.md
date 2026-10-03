# Campaign scripts (2026-10-03)

How the first Mode B end-to-end campaign was run, so it can be repeated or extended. These are dev tools, not part of
the product, and they use fixed paths under `C:\Work\ForgeRuns` (workspaces, an isolated Forge home, screenshots).

- `req_*.txt`: the original requirements (attendance system, bakery website, invoice extraction tool).
- `enhancements/`: each enhancement round (`enh_*`) and each piece of user feedback (`fb_*`) given to Forge.
- `drive_forge.py <workspace> <prompt_file> <result_json>`: runs Forge like `forge run --auto-approve`, and also
  approves `pip install` into the workspace environment (always-ask, so plain headless mode refuses it).
- `verify_attendance.py`, `verify_bakery.py`, `verify_invoice.py <app_dir> <python> <phase>`: independent Playwright
  checks (Edge, headless); the phase number includes the checks of every enhancement up to that round.
- `invoices/`: sample invoices (three layouts, a PDF, a note that is not an invoice).

Create a workspace with `forge new --standalone --project NAME --workspace PATH` (set `FORGE_HOME` to a scratch folder and
`FORGE_ENV_FILE` to the repo `.env`), then run `drive_forge.py` for the requirement and for each enhancement.
