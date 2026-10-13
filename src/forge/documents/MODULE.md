# documents

Word documents (TODO W1, D-342): an outline (`spec.py`, JSON or YAML) becomes a real .docx (`build.py`, python-docx, optional extra `forge[docs]`) with
headings, paragraphs (bold, italic, safe links), bullet and numbered lists, tables with a repeating header row, pictures with alt text, quotes,
page breaks, a table of contents field, header, footer and page-number field, language and title, optionally on a company template. `read.py` gives
Markdown with the comments and the count of tracked changes; `edit.py` replaces text across runs, sets or deletes paragraphs and adds comments while
keeping formatting; `check.py` finds structure and accessibility problems. The tools are in `tools/document.py`; the skill is `skills/make-document/SKILL.md`.

- **Depends on:** errors
- **Invariants:** python-docx is imported lazily (a missing library is a clear message); links may only be https, http or mailto; macros are never run or kept (result is always .docx); a picture without alt text is reported; a template's styles, header and footer are kept and its sample body text removed.
- **Tests:** test_documents.py
- **Decisions:** docs/DECISIONS.md (D-342); clean-room rules in docs/DOCUMENTS_CLEAN_ROOM.md.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
