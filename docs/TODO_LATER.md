# Parked for later

Things the user asked about and chose NOT to do yet. Nothing here is started. Each item says what it is, how big it is
and what to decide when it is picked up again. (The build plan itself is in `TODO.md`.)

## Rename Forge to "DebCraft" (asked 2026-10-09, parked)

Sizing done on 2026-10-09 (counts from `git grep`, excluding the built UI and test artifacts):

| Part | Size | Risk |
|---|---|---|
| Visible name: web UI (111 lines in `ui-react/src`), window title, system prompts, CLI help, install and start scripts, docs (464 lines) | about 700 lines in about 470 files | Low |
| Code package `forge` -> `debcraft`: 1,184 import lines, 218 source files, 131 test files, `pyproject.toml` name and the `forge` command, `MODULE.md` files, the module-boundary test | scripted, about half a day with the full test suite | Medium |
| Data and file names: `%USERPROFILE%\.forge` (accounts, memory, skills, `.env`), the `.forge` folder in every project (313 refs), `FORGE.md` instruction files (85 refs), `FORGE_*` settings (107 refs) | needs a migration or a read-the-old-name fallback, on the build machine and the office laptop | High |

Recommended plan when picked up (the user has not approved it yet):
1. Rename only what people see to DebCraft: UI, window title, prompts (what the model calls itself), install and start scripts, docs.
2. Add a `debcraft` command next to `forge` (a second entry in `[project.scripts]`), so `debcraft ui` works.
3. Rename `Start-Forge.cmd` to `Start-DebCraft.cmd` (and update `docs/INSTALL.md`).
4. Keep the internal names: package `forge`, `.forge` folders, `FORGE.md`, `FORGE_*` settings (nothing visible, nothing breaks).
5. The full internal rename is a separate, later decision; if done, read the old names as a fallback so existing data keeps working.

Decide when picking it up:
- Does `FORGE.md` (the instruction file) become `DEBCRAFT.md`? Both names would have to be read.
- GitHub repository name: renaming it on GitHub is a separate step by the user (the old link keeps redirecting).
- The zip folder name users download changes from `forge-main` to the new repository name (the start file works from any folder).
- Decisions in `docs/DECISIONS.md` keep saying "Forge" (history); add one new decision for the rename.
