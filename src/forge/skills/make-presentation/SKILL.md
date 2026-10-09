---
name: make-presentation
description: Make a clear, well-designed PowerPoint (.pptx) deck: plan the story, write an outline, build it with build_presentation, look at every slide with preview_presentation and fix what is wrong
---

# Making a presentation

Use this when the user asks for slides, a deck, a presentation or a .pptx. You build a real, editable PowerPoint file.
Do not describe slides in chat instead, and do not make a deck out of pictures of text.

## 1. Plan the story before any slide

Ask yourself (and the user, if it changes the deck and you cannot tell): who is the audience, what should they
think or do afterwards, how long is the talk (about one slide per minute, fewer for a decision meeting).
If the user gave a document, data or notes, read them first; the deck says what they say, never invented facts or
numbers. When a number or claim is missing, leave it out or mark it "to confirm" in the speaker notes.

A good deck has one thread: situation, the point, the evidence, what to do next. Typical shape: title, the
answer or main message up front, 3-6 content slides each making one point, a "next steps" or decision slide,
optionally a closing slide. A section slide only when the deck has distinct parts (more than about 8 slides).

## 2. Write the outline file

Write `docs/<name>-outline.json` (or `.yaml`) with `write_file`. Fields: `title`, optional `subtitle`, `author`,
`theme` (`clean`, `dark` or `warm`) and `footer`, then `slides`, each with a `layout` and optional `notes`
(speaker notes: what to say, sources, caveats).

Layouts and their fields:

| layout | use it for | fields |
|---|---|---|
| `title` | the first slide | `title`, `subtitle` |
| `section` | a divider between parts | `title`, `subtitle` |
| `bullets` | a point with 2-5 supporting lines | `title`, `bullets` (strings, or `{"text", "sub": [...]}`) |
| `two_column` | compare two things | `title`, `left` / `right`: `{"heading", "bullets"}` |
| `stats` | 1-4 headline numbers | `title`, `items`: `{"value": "42%", "label": "..."}` |
| `chart` | a trend or comparison | `title`, `kind` (`column`, `bar`, `line`, `pie`), `categories`, `series`: `{"name", "values"}`, `caption` |
| `table` | exact values, up to ~8 rows | `title`, `columns`, `rows`, `caption` |
| `image` | a screenshot, diagram or photo | `title`, `image` (workspace path), `alt`, `caption` |
| `quote` | one memorable sentence | `quote`, `by` |
| `closing` | the last slide | `title`, `subtitle` (contact) |

## 3. Design rules (the tool applies the look; you supply good content)

- **The title is the message.** Write titles as sentences that state the takeaway ("Search is now 4x faster"),
  not topics ("Search"). Under 12 words.
- **One idea per slide.** If a slide needs two headlines, make two slides.
- **Few words.** At most 5 bullets, each a short phrase (under about 12 words), not a sentence paragraph.
  Put detail in the speaker notes, not on the slide.
- **Show numbers, do not describe them.** A trend over time is a `line` or `column` chart; shares of a whole a
  `pie` (at most 5 slices); a few big figures `stats`; exact values a `table`. Put the unit and source in the
  `caption`. Never invent data to fill a chart.
- **Consistency.** Same theme for the whole deck; do not mix many layouts without reason.
- **Readable.** The builder will not go below 16 pt; if text does not fit it says so: split the slide or cut words.
  Do not fight it by cramming.
- **Images** need `alt` text saying what they show. Use pictures that carry meaning, not decoration.
- **Speaker notes** on every content slide: the sentence you would say, and the source of any number.

## 4. Build, look, fix

1. `build_presentation(outline=..., output="docs/<name>.pptx")`. Read the warnings; fix each in the outline and
   build again (they are about text too long, too many bullets, a table too tall, ...).
2. `preview_presentation(path=...)` makes a picture per slide with PowerPoint. Look at **every** slide with
   `view_image` and ask: is the text cut off or crowded, is anything unbalanced or empty, is the chart readable,
   does the title say the point? Fix and rebuild. Do this at least once; repeat until nothing is wrong.
3. If preview says PowerPoint is not available, say so plainly to the user ("I could not look at the slides, only
   check them by rule") and still go by the warnings.
4. Finish by telling the user where the file is, how many slides, the story in two lines, and anything you were
   unsure of or left as "to confirm". Offer a change of theme or a shorter version.

If `build_presentation` says python-pptx is not installed, tell the user the one command that fixes it
(`pip install python-pptx`) instead of trying to work around it.

## 5. Existing decks and company templates

**Summarise or review a deck:** `read_presentation(path)` lists every slide (layout, title, text, tables, chart
numbers, picture alt text, speaker notes). Base what you say on that, slide by slide; say when a slide has
nothing to read (a picture without alt text, for instance). Never guess what a slide says.

**Change a deck:** read it first, then `edit_presentation(path, operations=[...], output=...)`. It keeps the deck's
own formatting, so prefer it over rebuilding whenever someone else made the deck or a template is involved.
Operations: `replace_text`, `set_text`, `set_notes`, `delete_slide`, `move_slide`, `duplicate_slide`,
`add_slide`, `update_chart`, `update_table`. Give `output` (a new file name) unless the user asked to change the
file itself; in place is allowed and can be undone. If one operation fails, nothing is saved and the message
says which: fix that one and send the list again. Afterwards `preview_presentation` and look at the changed
slides (a longer sentence in a fixed box can overflow; PowerPoint will not warn you).

**Use a company template** (a `.potx`, or any `.pptx` with the right masters): `read_presentation(template)` shows
its layout names and placeholders. Then `edit_presentation(template, output="docs/new.pptx", operations=[
add_slide ... for each slide, then delete_slide for the template's sample slides])`. Use the template's layout
names (for example "Title and Content") and put text in its placeholders (`title`, `body`, and `placeholders`
by number for the rest). Do not rebuild a template deck with `build_presentation`: that ignores its look.

Limits to tell the user plainly: copying a slide that holds a chart or an embedded object is not possible (build
it again with `add_slide` and `update_chart`); animations, comments and slide-master changes are not edited;
`.ppt`, `.pptm` and password-protected files cannot be opened.
