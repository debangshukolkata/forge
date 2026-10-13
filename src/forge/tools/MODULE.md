# tools

The tool implementations the agent can call (files, search, shell wrappers, KB, DB, web, browser, verify, vision, Mode B, learning) and the registry that lists them.

- **Web (D-209):** `web.py` (the tools and search providers), `web_chain.py` (fetch stages), `web_guard.py` (address policy),
  `web_extract.py` (HTML/PDF to text), `web_render.py` (read-only headless browser). A fetch never ends in nothing: see DECISIONS D-209.
- **Web UI quality (D-245..D-254):** `browser.py` (`browser_screenshot` scrolls the page so scroll reveals play, saves the picture, runs the style audit, flags a picture identical to another page's, takes `width`/`height`), `ui_audit.py` (the in-page audit: unstyled CSS framework, contrast with oklch/color-mix read through a canvas, overflow, default controls, see-through sticky bars, invisible form fields, clipped text, taste checks, plus a static source scan and `tailwind_setup_problem`), `show_app.py` (opens the running app after proving it is the app; tries 127.0.0.1, localhost and [::1]), `vision.py` (`view_image` now reports the image path so the chat can show it).
- **Depends on:** config, db, doctor, environment, errors, llm, net, memory, modeb, parity, safety, slides, toolkit, vision, workspace
- **Invariants:** Each tool has pydantic Args, a one-line summary() and a read_only flag. Errors become ToolResult(ok=False). Tools that start agents live in forge.agent, not here.
- **Tests:** test_context.py, test_contracts.py, test_db.py, test_frontend_setup.py, test_hardening.py, test_kb.py, test_learning.py, test_live_verify.py (+9 more)
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
- **Pictures (D-326..D-328):** `imagegen.py` (`generate_image`, Gemini/Imagen on Vertex AI), `findimage.py` (`find_image`, `fetch_image`), `image_sources.py` (Iconify, Openverse, Wikimedia, NASA, Pexels, Unsplash, Pixabay with licence filter), `picture_library.py` (pictures kept for offline reuse); `scripts/dev/reach_smoke.py` checks what the machine can reach.
