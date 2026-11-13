# toolkit

Tool runtime primitives: Tool/ToolContext/ToolResult contract, shell and PowerShell runners, background processes, and
`app_keys` (the Azure model the user lets the app under test use, D-466; any other value of the .env a command needs, by name, after one card and read when each command starts, never one of DebCraft's own names, D-569, D-570; `app.env`, the user's file whose values reach every command without a question, the facts about the installation that end the system prompt, and the token form remembered per project, D-571; `shell.py` adds a note to a command that looks for a name of the .env it was not given), `private_env` (the names DebCraft itself uses are removed from the environment commands inherit, D-202; the names its configuration reads are cached by the modified time of `config.yaml`, D-573).

- **Depends on:** config, errors, llm, net, safety, workspace
- **Invariants:** Tools never write outside the workspace jail. Capabilities (verify, vision, parity) build on this, not on forge.tools.
- **Tests:** test_context.py, test_contracts.py, test_db.py, test_frontend_setup.py, test_hardening.py (and others; see tests/)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **App logins (D-603):** `app_logins.py`: `<DebCraft Home>/app_logins.yaml` (the environments the user describes: login address, steps, where the token is, its name), `TokenStore` (`tokens.json`, expiry from the JWT, registered with the redactor, never an env file) and the host lookup that makes the listed hosts the only remote hosts `http_request` may call.
