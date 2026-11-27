# workspace

The per-requirement workspace: copy, baseline manifest, the single write gate (jail + checkpoint), output/ builder, checkpoints, Python/Node environment detection, read grants (`read_grants.py`: read-only places the user opened, D-208).

- **Depends on:** errors, home_layout, safety
- **Invariants:** Every write goes through Workspace (safety invariant 1); the one exception is `to_repository.py` (D-674), called only from the web app's red card on the user's click. Preserve BOM and line endings.
Changed expectations in the user's existing tests are recorded for the delivery report (`test_expectations.py`, D-560).

- **Tests:** test_agent_loop.py, test_context.py, test_contracts.py, test_db.py, test_diagnose.py, test_frontend_setup.py (and others; see tests/)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Attachments (D-469):** `Workspace.input_path` resolves `.forge/inputs/...` and `.forge/tool_outputs/...` for reading only; `read_file` and `list_dir` use it.
- **Conversations (D-582):** `conversations.py`: `ConversationStore` (index, folder per conversation under `.forge/conversations/`, copy-migration of the old log and task state into `c1`, id check before any path is built) and `conversation_file` (where a log or state file is, read without changing anything).
- **Run notes (D-597):** `run_notes.py`: `RunNotes` keeps in `.forge/run_notes.json` the processes that reached their ready state and the HTTP calls that worked (names of settings and token variables only, redacted); `render()` is the pinned block "How this project was run before".
- **Temporary changes (WF2, D-622):** `temporary_edits.py`: `TemporaryEdits` keeps in `.forge/temporary_edits.json` the changes made only to investigate, each as blocks (`old`, `new`, up to three unchanged lines around); `take_out` sets a block back when it is found exactly once, requiring fewer surrounding lines when those changed. `output.py` delivers a marked file without those changes (`delivered_bytes`, encoding and line endings kept), leaves out a file that is temporary as a whole, lists them in `CHANGES.md` and `MANIFEST.json`, and warns in `CHANGES.md` and `COPY_INSTRUCTIONS.md` about one it could not take out. The copy keeps the change.
- **Copy to source (D-674):** `to_repository.py`: `plan_copy`, `copy_to_repository` (backup under `.forge/repo_copies/`), `undo_copy`.
