# pdfs

PDF toolkit (TODO W3, D-343): `read.py` (pypdf) gives text per page in reading layout, metadata, form fields, images, and says when a file is a scan or
protected; `edit.py` merges, splits, rotates, crops, deletes or extracts pages, stamps a watermark or page numbers (reportlab overlay), fills form fields,
encrypts and decrypts; `build.py` creates a PDF from an outline (reportlab platypus: headings, paragraphs, lists, tables, pictures, page breaks) with the title
and language set. The tools are in `tools/pdf_toolkit.py`; the skill is `skills/pdf-toolkit/SKILL.md`. Rendering pages and OCR use the existing `pdf_render`
and `ocr_image`.

- **Depends on:** brand, errors
- **Invariants:** pypdf and reportlab are imported lazily (a missing library is a clear message); the original file is never changed (results are new bytes the tool writes through the workspace); an encrypted file is opened only with the password the user gave; links in a built PDF may only be https, http or mailto; JavaScript and launch actions in an opened PDF are never run (pypdf does not run them) and are reported by `read_pdf`.
- **Tests:** test_pdfs.py
- **Decisions:** docs/DECISIONS.md (D-343); clean-room rules in docs/DOCUMENTS_CLEAN_ROOM.md.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
