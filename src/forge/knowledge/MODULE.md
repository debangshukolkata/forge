# knowledge

What DebCraft knows about an existing repository between projects (TODO section 0h, D-563). Step KL1 is the structure index: exact facts read from the code without a model.

- `python_file.py`: one Python file read with `ast`: symbols with signatures, the names each function calls and uses, FastAPI and Flask endpoints (decorators, MethodView classes, `add_url_rule`, `add_api_route`, `add_resource`), router and blueprint prefixes and mounts, payload schemas and request keys, auth decorators and dependencies, model fields and table names, SQL text, environment variable names (never values).
- `structure.py`: the stored index (`structure.json` in `<DebCraft Home>/memory/scopes/<repository>/knowledge/`), one record per file with a fingerprint; `refresh` parses only files whose content changed and keeps the stored record of files the current project itself has changed. Also `.sql` files (created tables) and `.ts` files (exported symbols, Angular selector, HTTP calls).
- `code_map.py`: `CodeMap` resolves names through imports and re-exports into links between files (calls and uses, each `exact` or `by name`), builds full endpoint paths, payloads, auth checks with the environment names they read, and the tables an endpoint reaches with the call chain.

- `topics.py` (KL2, D-566): topic notes, one Markdown file per topic under `knowledge/topics/` with a YAML header (title, summary, source files with fingerprints, updated, history of corrections); search, the pinned index lines with "may be outdated" marks, and the folders no topic covers.

- **Depends on:** (nothing)
- **Invariants:** Never writes into the user's repository or a workspace: only under DebCraft Home. Stores names, signatures, paths and line numbers; no code bodies and no values of environment variables. A link that is not proven by an import is labelled `by name`. The index describes the user's repository: files the project has changed keep their stored record.
- **Tests:** test_knowledge_structure.py, test_knowledge_topics.py
- **Decisions:** docs/DECISIONS.md D-563; layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
