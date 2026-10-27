# tools

The tool implementations the agent can call (files, search, shell wrappers, KB, DB, web, browser, verify, vision, Mode B, learning) and the registry that lists them.

- **Web (D-209):** `web.py` (the tools and search providers), `web_chain.py` (fetch stages), `web_guard.py` (address policy),
  `web_extract.py` (HTML/PDF to text), `web_render.py` (read-only headless browser). A fetch never ends in nothing: see DECISIONS D-209.
- **Web UI quality (D-245..D-254):** `browser.py` (`browser_screenshot` scrolls the page so scroll reveals play, saves the picture, runs the style audit, flags a picture identical to another page's, takes `width`/`height`), `ui_audit.py` (the in-page audit: unstyled CSS framework, contrast with oklch/color-mix read through a canvas, overflow, default controls, see-through sticky bars, invisible form fields, clipped text, taste checks, plus a static source scan and `tailwind_setup_problem`), `show_app.py` (opens the running app after proving it is the app; tries 127.0.0.1, localhost and [::1]), `vision.py` (`view_image` now reports the image path so the chat can show it).
- **Depends on:** brand, config, db, designsystem, doctor, documents, environment, errors, llm, net, memory, modeb, ooxml, parity, pdfs, safety, sheets, slides, toolkit, vision, workspace
- **Invariants:** Each tool has pydantic Args, a one-line summary() and a read_only flag. Errors become ToolResult(ok=False). Tools that start agents live in forge.agent, not here.
- **Tests:** test_context.py, test_contracts.py, test_db.py, test_frontend_setup.py, test_hardening.py (and others; see tests/)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Pictures (D-326..D-328):** `imagegen.py` (`generate_image`, Gemini/Imagen on Vertex AI), `findimage.py` (`find_image`, `fetch_image`), `image_sources.py` (Iconify, Openverse, Wikimedia, NASA, Pexels, Unsplash, Pixabay with licence filter), `picture_library.py` (pictures kept for offline reuse); `scripts/dev/reach_smoke.py` checks what the machine can reach.
- **Fonts (D-330):** `fonts.py` (`find_font`, `fetch_font`), `font_sources.py` (Fontsource catalogue, licence filter, @font-face CSS); `slides/installed_fonts.py` tells which fonts this Windows computer has.
- **Archives and app keys (D-461, D-466):** `archive.py` (one tool: list or extract zip and tar into `.forge/inputs/<name>/` or a workspace folder, with entry, size and path limits) and `app_keys_tool.py` (`request_app_keys`). `ocr_image` and `ocr_pdf` are registered only when Tesseract is ready. A request carries at most 128 tools: `registry.LEAVE_OUT_FIRST` (D-462).
- **Theme inspiration (D-492):** `theme_search.py` (`theme_search`: search, read-only study, clean-room check) and `theme_sources.py` (the public theme lists, GitHub and WordPress.org package reads, the facts a study keeps, the fingerprint and overlap). Skill `theme-inspiration`; protocol docs/THEME_CLEAN_ROOM.md.
- **Code outline (C11, D-498):** `code_outline.py` (`code_outline`): signatures and line numbers of a file or folder (Python by `ast`, other languages by pattern) and `callers` of a name; read-only, parses on demand, no index (D-156).
