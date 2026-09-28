# Installing and running Forge (Windows, no admin rights)

This guide is for installing Forge on a work laptop that may have no internet access for `pip` and no
administrator rights. Everything installs into your user profile.

## What you need

| Item | Where it comes from |
|---|---|
| Python 3.13 (64-bit), installed for your user only | python.org installer → untick "for all users"; tick "Add to PATH" or use the `py` launcher |
| The Forge wheelhouse folder (`wheels\`) | built on a machine with internet: `scripts\build_wheelhouse.ps1` |
| `install_forge.ps1` | `scripts\install_forge.ps1` from the Forge repository |
| Azure OpenAI endpoint, deployment name, API version, key | your Azure portal / platform team |
| Optional: a local Postgres URL, a read-only dev DB URL, a SerpAPI key | your team |

## 1. Build the wheelhouse (on a machine with internet)

```powershell
cd <forge repository>
powershell -ExecutionPolicy Bypass -File scripts\build_wheelhouse.ps1                   # wheels\ with mcp + browser extras
powershell -ExecutionPolicy Bypass -File scripts\build_wheelhouse.ps1 -IncludeBrowser   # also stores Chromium for the browser tool
```

The script downloads binary wheels for CPython 3.13 / win_amd64 only (nothing is compiled on the laptop),
writes `SHA256SUMS.txt`, then proves the set is complete by installing it into a clean venv with
`--no-index` and running `forge --version` and `forge doctor --offline`.

Copy `wheels\`, `scripts\install_forge.ps1` and this file to the laptop (USB drive, OneDrive, a network share).

## 2. Install (on the laptop)

```powershell
powershell -ExecutionPolicy Bypass -File install_forge.ps1 -Wheelhouse .\wheels
```

It checks the wheel hashes, creates `%LOCALAPPDATA%\Forge\venv`, installs Forge offline, creates
`%USERPROFILE%\.forge\.env` (a template; an existing one is kept), copies Chromium if the wheelhouse has it,
and writes `%LOCALAPPDATA%\Forge\bin\forge.cmd`.

Then:
1. Add `%LOCALAPPDATA%\Forge\bin` to your **user** PATH: Start → "Edit environment variables for your
   account" → Path → New.
2. Open `%USERPROFILE%\.forge\.env` in Notepad and fill in the `AZURE_OPENAI_*` values. Keep this file
   private; Forge never shows its values to the model, in logs or in the browser.
3. Open a **new** PowerShell window and run `forge doctor`. Every line should be OK, apart from optional
   items you don't use (for example, databases).

If PowerShell blocks scripts, the `-ExecutionPolicy Bypass` above applies to that single run only and needs
no admin rights. If Python's installer isn't allowed either, ask IT for "Python 3.13 per-user".

## 3. Use it

```powershell
forge ui                                   # the web UI (opens Edge on 127.0.0.1): New project = name + folder (+ repo in Mode A)
forge ui --react                           # the new React UI on port 8766 (the classic one stays on 8765)
forge                                      # the terminal UI: asks Mode A (a repository) or Mode B (standalone)
forge new --project claims-export --repo C:\src\myrepo --workspace C:\forge-ws\req1   # Mode A: works on a copy
forge new --standalone --project payments-masking --workspace C:\forge-ws\pm1       # Mode B: never sees your code
forge run --workspace C:\forge-ws\req1 -p "the requirement text"                  # headless
forge doctor                               # check the setup any time
```

Forge works in a per-requirement workspace (the folder you pass to `--workspace`; your repository is only
read, never written) and delivers the changed files plus `COPY_INSTRUCTIONS.md` in the workspace's
`output\` folder. You copy them into your repository yourself.

## Upgrading

Build a new wheelhouse, copy it over and run `install_forge.ps1` again. Your `.env`, `config.yaml`,
workspaces, knowledge bases and lessons are kept.

## Uninstalling

Delete `%LOCALAPPDATA%\Forge` (the program) and, if you also want to remove your data, `%USERPROFILE%\.forge`.
Remove the PATH entry.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `forge` is not recognised | Open a new PowerShell after editing PATH, or run `%LOCALAPPDATA%\Forge\bin\forge.cmd` directly |
| `pip ... No matching distribution` during install | The wheelhouse was built for another Python version: rebuild with `-PythonVersion 3.13` |
| `Hash mismatch for ...` | The copy is damaged: copy the `wheels\` folder again |
| `forge doctor`: model check fails with 401/404 | Wrong key or deployment name in `.env` |
| Browser tool says Playwright is missing | Rebuild the wheelhouse with `-IncludeBrowser`, or ignore it (only the browser tool needs it) |
| Company proxy blocks Azure | Set `HTTPS_PROXY` for your user; ask IT for the proxy address |
