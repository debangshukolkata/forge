---
name: make-document
description: Build, read, edit and check Word documents (.docx): reports, memos, proposals, letters. Use when the user wants a Word document or wants an existing one changed.
---

# Making Word documents

Tools: `build_document` (from an outline), `read_document`, `edit_document`, `check_document`. Written for DebCraft from the Office Open XML
specification, the python-docx documentation and our own tests with Word.

## What a good document does
1. **Story first.** Decide the one thing the reader should know or do, say it in the first paragraph (a summary), then support it. Headings are
   the outline of that story: a reader should get the argument from the headings alone.
2. **Real structure.** Use heading levels in order (1, then 2, never 1 then 3), real lists, real tables with a header row, a table of contents
   (`toc: true`) for anything over about five pages. Never fake a heading with bold text or spacing with empty paragraphs: `check_document` reports both.
3. **Short paragraphs** (3 to 5 lines), plain words, one idea each. Numbers with their unit and source; tables for comparisons, a sentence for one fact.
4. **Consistent look:** one font (default Calibri 11), spacing from styles, nothing hand-formatted twice. With a company template (`template` in the
   outline) its styles, header and footer are kept and its sample text is removed: use its styles by writing the same structure.
5. **Accessible:** title and language set (the outline does it), alt text on every picture (required in the outline), descriptive link text
   ("the 2025 budget", not "click here"), tables with a repeating header row (done for you).
6. **Facts only from the sources.** When the content comes from files, read them first (`read_source_document`, `read_document`, `read_workbook`);
   never invent numbers; cite where a figure came from.

## Outline format (JSON or YAML)
```json
{"title": "Quarterly report", "author": "Finance", "language": "en-GB", "toc": true,
 "header": "Confidential", "footer": "Acme", "page_numbers": true, "template": null,
 "blocks": [
  {"type": "heading", "level": 1, "text": "Summary"},
  {"type": "paragraph", "runs": [{"text": "Sales rose "}, {"text": "12%", "bold": true}, {"text": ", see "}, {"text": "the dashboard", "link": "https://example.com"}]},
  {"type": "bullets", "items": ["one", "two"]},
  {"type": "numbered", "items": ["first", "second"]},
  {"type": "table", "header": ["Region", "Q1"], "rows": [["North", "100"]], "caption": "Table 1: Sales"},
  {"type": "image", "path": "docs/chart.png", "alt": "Bar chart of sales by region", "width_in": 5.5, "caption": "Figure 1"},
  {"type": "quote", "text": "..."}, {"type": "page_break"}]}
```
Plain text goes in `text`; use `runs` only for bold, italic or links (https, http or mailto only). The table of contents and page numbers are Word
fields: Word fills them when the file is opened (the user may be asked to press F9 / Update field).

## Work loop
1. Write the outline, `build_document`; fix every problem its result lists and build again.
2. Changing an existing document: `read_document` first (comments and tracked-change counts are shown; deleted text is not), then `edit_document`.
   `replace_text` works across Word's split runs and in tables, headers and footers; paragraph numbers are those of `read_document`'s non-empty paragraphs.
   Do not accept or reject the user's tracked changes yourself; mention them.
3. **Look at it.** `preview_file` makes pictures of the pages with Word itself (LibreOffice if Word is missing) and one contact sheet; `view_image` them: headings not
   stranded at a page bottom, tables not split badly, pictures sized, header and footer right. It can also save the PDF (`pdf_output`). If it says neither
   is available, say that the layout was not looked at. When the document matters (sent to a customer, a board), run `critique_document` too and fix the
   high and medium issues (at most three rounds).
   Footnotes: `footnote` on a run in the outline, or `add_footnote` on a paragraph of an existing file. Tracked changes: `accept_changes` and
   `reject_changes` settle all of them at once; only do this when the user asked, and tell them how many were settled.
4. A picture for the document: make it first (chart, `findimage`, `generate_image`), then put it in with alt text.
5. In your answer say what the document contains and which facts came from which source; say that the contents list fills when opened in Word.

## Do not
- Do not paste long text as one paragraph, do not use tables for layout, do not leave template sample text.
- Do not write macros; the result is always `.docx`.

## Start from a template, and the company look
- Look for a ready template first: `find_asset` (type `template`, e.g. "business report", "memo", "proposal") and `add_asset` copy a tested .docx into the
  project; put its path in `template`. Its styles, header and footer are kept and its sample text is removed.
- The company look: `brand` in the outline, or `brand_file` (a JSON file with `accent`, `text`, `title_font`, `body_font`) on the build tool. Headings,
  table headers and fonts follow it; a colour that would be unreadable on white is darkened. The same file works for decks, workbooks and PDFs.

## Gotchas
- The outline's `title` is printed as the document's title for you. Start `blocks` with the first section heading: repeating the title as a heading shows it twice.
