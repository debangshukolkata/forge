# memory

Auto-memory like Claude Code (D-156): one Markdown file per memory (frontmatter: name, description, type user/feedback/project/reference) plus a MEMORY.md index, in two scopes: user (everywhere) and project (one repository or host profile, `scope.py`). The model writes memories itself with `memory_write`; the index is pinned every session. Also custom slash commands.

- **Depends on:** safety, workspace
- **Invariants:** Memories are redacted before saving and never hold secrets, code or data rows. Project scope never crosses between repositories or profiles. Stored under Forge Home only.
- **Tests:** test_m10_tools.py, test_memory_store.py
- FORGE.md shares the project folder but is the instructions, not a note: the store skips it (D-199).
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
