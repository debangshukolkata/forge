---
name: make-presentation
description: Use when the user asks for slides, a deck, a presentation or a .pptx (new, edited, restyled or built on a company template): plan the story, build it, look at every slide and fix what is wrong
---

# Making a presentation

Use this when the user asks for slides, a deck, a presentation or a .pptx. You build a real, editable PowerPoint file.
Do not describe slides in chat instead, and do not make a deck out of pictures of text.

## 1. Plan the story before any slide

Ask yourself (and the user, if it changes the deck and you cannot tell): who is the audience, what should they
think or do afterwards, how long is the talk. **One content slide per two or three minutes** (a 20 minute talk: 7 to 10 slides; a 45 minute
training or workshop: 12 to 18, because exercises and discussion take time that slides do not; a 15 minute briefing: 5 to 8).
Put the length in the outline as `"minutes": 20`: the build warns when the deck is too long for it. Detail that does not fit goes
in the speaker notes or an appendix, not on more slides.
If the user gave a document, data or notes, read them first; the deck says what they say, never invented facts or
numbers. When a number or claim is missing, leave it out or mark it "to confirm" in the speaker notes.

A good deck has one thread: situation, the point, the evidence, what to do next. Typical shape: title, the
answer or main message up front, 3-6 content slides each making one point, a "next steps" or decision slide,
optionally a closing slide. A section slide only when the deck has distinct parts (more than about 8 slides).

## 2. Write the outline file

Write `docs/<name>-outline.json` (or `.yaml`) with `write_file`. Fields: `title`, optional `subtitle`, `author`,
`theme` (one of the 19 below) and `footer`, then `slides`, each with a `layout` and optional `notes`
(speaker notes: what to say, sources, caveats).

Layouts and their fields:

| layout | use it for | fields |
|---|---|---|
| `title` | the first slide | `title`, `subtitle` |
| `section` | a divider between parts | `title`, `subtitle` |
| `bullets` | a point with 2-5 supporting lines | `title`, `bullets` (strings, or `{"text", "sub": [...]}`) |
| `two_column` | compare two things | `title`, `left` / `right`: `{"heading", "bullets"}` |
| `stats` | 1-4 headline numbers | `title`, `items`: `{"value": "42%", "label": "..."}` |
| `cards` | 2-4 parallel points (reasons, benefits, options, pillars) instead of a bullet list | `title`, `items`: `{"heading", "text"}`, optional `numbered: true` |
| `steps` | a process, plan or rollout of 2-5 steps in a row | `title`, `steps`: `{"heading", "text"}` |
| `chart` | a trend or comparison | `title`, `kind` (see Charts below), `categories`, `series`: `{"name", "values"}`, `caption`, more options below |
| `table` | exact values, up to ~8 rows | `title`, `columns`, `rows`, `caption` |
| `image` | a screenshot, diagram or photo | `title`, `image` (workspace path), `alt`, `caption` |
| `quote` | one memorable sentence | `quote`, `by` |
| `closing` | the last slide | `title`, `subtitle` (contact) |
| `freeform` | a designed slide you lay out yourself: cover, diagram, timeline, comparison | `title`, `elements`: see section 6 |

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
- **Speaker notes** on every slide that has content, also slides copied from a template sample (`notes` on `template_slide`): what the speaker
  says, the source of any number, and for a workshop or training what the facilitator does and the timing. The build warns about slides with
  no real notes.

### Choose the theme from the topic (19 themes, all checked for readable contrast)
Pick by audience and subject, not by habit; do not use `clean` just because it is first. One main colour plus one accent.

| theme | mood | fits |
|---|---|---|
| `clean` | neutral, crisp, business | business, report, update, general |
| `dark` | dark, focused, technical | keynote, product, launch, demo |
| `warm` | warm, human, editorial | story, people, community, culture |
| `forest` | natural, calm, grounded | sustainability, nature, agriculture, environment |
| `ocean` | fresh, clear, open | travel, water, marine, shipping |
| `sunset` | energetic, creative, friendly | marketing, creative, events, consumer |
| `slate` | formal, sober, trustworthy | finance, legal, consulting, government |
| `midnight` | premium, serious, confident | premium, luxury, investor, finance |
| `paper` | editorial, scholarly, calm | education, research, humanities, books |
| `mint` | healthy, light, caring | health, wellness, hospital, nutrition |
| `plum` | expressive, cultural, refined | arts, culture, fashion, beauty |
| `terracotta` | earthy, crafted, welcoming | architecture, craft, food, hospitality |
| `mono` | minimal, stark, modern | minimal, architecture, design, portfolio |
| `sky` | open, friendly, technical | technology, education, saas, startup |
| `coral` | playful, bright, approachable | kids, children, food, retail |
| `graphite` | technical, sharp, modern | developer, engineering, data, ai |
| `ruby` | urgent, human, committed | charity, health, donation, emergency |
| `olive` | grounded, heritage, quiet | heritage, outdoors, farming, craft |
| `indigo` | bold, imaginative, night | ai, creative, events, gaming |

**A brand kit** overrides the theme when the user has brand colours or fonts: `"brand": {"accent": "#E4002B", "background": "#FFF4E5",
"title_font": "Georgia", "body_font": "Calibri"}` (any subset; the rest is derived so text stays readable). The build warns when brand
colours are hard to read or a font is not on every computer. If the project has a brand file, copy its values here.

### Avoid the generated look (the build warns about most of these)
- **No decoration under titles.** No accent bar or line under a title; the title and white space are enough.
- **Do not default to one blue.** Pick the theme and accent for the audience and topic; use one accent plus neutrals.
- **Vary the layout.** Never three of the same layout in a row; mix chart, stats, two-column, picture and freeform slides.
- **Match the content to a layout, do not default to bullets.** Choose by what the content IS:
  a few parallel points (3 to 4 pillars, benefits, options) -> `cards`;
  steps, a process, a rollout -> `steps` (or a `process` or `timeline` diagram for more detail); a before/after, good/bad or A/B -> `two_column` or two cards;
  headline figures -> `stats`; a trend or share -> `chart`; a decision, ask or quote -> a big-type slide (one sentence, large) or
  `quote`; a system or flow -> a diagram recipe; exact values -> `table`. Plain `bullets` is for the one slide in four that is
  really a list. No more than two bullet slides in a row; at most about 40 percent of content slides.
- **Every content slide has a visual:** a chart, big numbers, a table, a picture or a drawn diagram. A deck that is mostly
  bullets is a document, not a presentation.
- **Dark and light sandwich:** dark title and closing slides with light content slides in between (or dark throughout), not a
  random mix.
- **Takeaway titles:** a sentence that says the point and at most 12 words. A bare topic word is flagged.
- **Fonts that exist everywhere:** Calibri and Georgia are used by the themes. In freeform text prefer Arial, Calibri, Cambria,
  Georgia, Times New Roman, Courier New. Other fonts may be replaced on the reader's computer and then text no longer fits.

## 4. Build, look, fix

1. `build_presentation(outline=..., output="docs/<name>.pptx")`. Read the warnings; fix each in the outline and
   build again (they are about text too long, too many bullets, a table too tall, ...).
2. `preview_presentation(path=...)` makes a picture per slide with PowerPoint, plus contact sheets (12 numbered slides per
   picture): look at the contact sheet first to judge flow, rhythm and whether it looks like one deck. Then look at **every** slide with
   `view_image` and ask: is the text cut off or crowded, is anything unbalanced or empty, is the chart readable,
   does the title say the point? Fix and rebuild. Do this at least once; repeat until nothing is wrong.
   With PowerPoint present the preview also lists, from PowerPoint's own measurements, every text box whose text is taller than its
   box (with the sizes in inches) and every table that grew past the slide: fix each one (enlarge the box, shorten the text, split the
   table), then preview again until it says all text fits.
3. If preview says PowerPoint is not available, say so plainly to the user ("I could not look at the slides, only
   check them by rule") and still go by the warnings.
4. Finish by telling the user where the file is, how many slides, the story in two lines, and anything you were
   unsure of or left as "to confirm". Offer a change of theme or a shorter version.

If `build_presentation` says python-pptx is not installed, tell the user the one command that fixes it
(`pip install python-pptx`) instead of trying to work around it.

## 4b. Accessibility (built in, check the rest)
Every deck the builder makes gets: the document title, the text language (`"language": "de-DE"` in the outline; default en-US), the title
first and the footer last in the reading order (only where moving them cannot change what is seen), a header row marked on tables, alt
text on charts and tables taken from the slide title. **You supply alt text for pictures** (`alt`), and you keep chart colours apart for
colour-blind viewers: the builder picks them for you from the theme (a combination that stays distinguishable for two or three series;
with more series add data labels). `check_accessibility(path)` lists what is missing in any deck (made elsewhere, or after edits):
fix every error; a warning is worth fixing when it is cheap.

## 4c. Slide features (only when the user asks for them)
Per-slide outline fields: `hidden: true` (backup slides, skipped in the show), `section: "Name"` (starts a section in the slide sorter),
`transition: "fade"|"push"|"wipe"|"split"|"cover"|"none"` (or `transition` on the deck for every slide), `animate: "appear"|"fade"|"wipe"`
(the slide's content, not its title, comes in together on one click). For anything finer use `edit_presentation` operations:
`hide_slide`, `set_transition` (speed, `advance_after` seconds), `animate` (one shape: effect and `on_click`/`with_previous`/
`after_previous`), `clear_animations`, `set_sections`, `add_comment` (a note to the reader, shown in the Comments pane).
`read_presentation` lists all of these. Default to none: motion that nobody asked for makes a deck look dated. Never animate text a
speaker reads from the slide line by line unless asked.

## 5. Existing decks and company templates
Reading a deck: `read_presentation` with `format: "markdown"` gives the text as Markdown (a heading per slide, bullets, tables, chart
data, links, notes, comments, hidden slides) which is the best form for summarising, rewriting or building a new deck from an old one.
`convert_presentation` turns an old `.ppt`/`.pptm` into `.pptx`, any deck into PDF, or (`to: "pictures"`) saves the embedded pictures as
files; the first two need PowerPoint, and without it you ask the user to use File > Save As.


**Summarise or review a deck:** `read_presentation(path)` lists every slide (layout, title, text, tables, chart
numbers, picture alt text, speaker notes). Base what you say on that, slide by slide; say when a slide has
nothing to read (a picture without alt text, for instance). Never guess what a slide says.

**New slides in an edited deck:** `add_slide` with only `title` and `body` copies the look of the deck's own last text slide (same
layout, boxes, fonts and positions) and puts the slide before a closing slide ("Thank you", "Questions"). **Do not add a `move_slide`
after it: the slide already lands in the right place** (the result says where). A `layout` name on a deck whose slides are not made of
placeholders (a deck DebCraft built) also copies the deck's look; add `exact_layout: true` to force the layout's own placeholders. Use
`like: N` to copy a particular slide, `at` for a position, `layout` for a company template's layout names. `replace_text` also changes
chart titles, axis titles, category and series names and picture alt text, so "replace every X" really means every one.

**Change a deck:** read it first, then `edit_presentation(path, operations=[...], output=...)`. It keeps the deck's
own formatting, so prefer it over rebuilding whenever someone else made the deck or a template is involved.
Operations: `replace_text`, `set_text`, `set_notes`, `delete_slide`, `move_slide`, `duplicate_slide`,
`add_slide`, `update_chart`, `update_table`, and (D-289) `replace_picture` (keeps crop and place), `format_text` (bold, italic, size, colour, font on a phrase, a shape or every slide), `set_theme` (heading/body font, theme colours), `add_table_row`/`delete_table_row`/`add_table_column`/`delete_table_column`, `change_chart_type`, `format_chart` (title, legend, labels, number format, colours), `set_footer` (footer text, slide numbers), `set_notes_bulk`, `delete_shape`, `remove_empty_placeholders`. A shape can be named `"text:some words"` to find it by what it says. Decks DebCraft built draw their own footer and numbers, so `set_footer` there would double them: change the outline and rebuild instead. Give `output` (a new file name) unless the user asked to change the
file itself; in place is allowed and can be undone. If one operation fails, nothing is saved and the message
says which: fix that one and send the list again. Afterwards `preview_presentation` and look at the changed
slides (a longer sentence in a fixed box can overflow; PowerPoint will not warn you).

**Use a company template** (a `.potx`, or any 16:9 `.pptx` with the right masters). The goal: a deck in the corporate format,
made of the template's own slides. Steps:
1. `analyze_template(path, pictures=true)`: size, theme colours, fonts, the layouts, and the template's SAMPLE SLIDES, each with its
   kind (title, section, bullets, two_column, cards, stats, steps, quote, thanks, chart, table, image_text) and its slots. Look at the
   contact sheet with `view_image` so you know what each sample looks like.
2. Write the outline with `"template": "path/to/template.potx"`. For each piece of content pick the sample that fits:
   - ordinary `title`, `section`, `bullets`, `two_column`, `stats` and `closing` slides are matched automatically to the template's
     own sample of that kind (several samples of a kind are used in turn); no sample of that kind: its layout is used.
   - for a sample that has no ordinary layout (cards, steps, agenda, image with text, a special design), copy it yourself:
     `{"layout": "template_slide", "source": 4, "fill": {"title": "...", "items": [{"heading": "...", "text": "..."}, ...]}}`.
     `fill` keys: `title`, `subtitle`, `body` (a list of lines; two leading spaces = sub-bullet), `items` (the repeated groups, each
     with the parts the analysis lists: `number`, `heading`, `text`; fewer items than groups removes the spare groups and centres
     the rest, more is refused: split the slide), `picture` (a workspace picture replacing the sample's), `slot:<id>` for anything else.
     A slot you leave out is removed, so no sample wording is ever left behind.
   - nothing in the template fits (a chart, a table, a diagram, a one-off design): use `chart`, `table`, `image`, `freeform`; they are
     drawn in the template's free area in its colours and fonts, with the decoration its samples share (company line, bars), so the
     slide still looks like part of the deck. Be creative there, but keep to the template's colours, fonts, margins and tone.
3. Build, then `preview_presentation` and look: every slide must look like the template's own work.
Never change the template's look to suit the content: change the content to suit the template (shorter text, split a slide).
Templates that are not 16:9 are refused; for those use `edit_presentation` (`add_slide` with the template's layout names, then
`delete_slide` for its samples). A `brand` kit in the outline still overrides colours and fonts.

Limits to tell the user plainly: copying a slide that holds a chart or an embedded object is not possible (build
it again with `add_slide` and `update_chart`); animations, comments and slide-master changes are not edited;
`.ppt`, `.pptm` and password-protected files cannot be opened.

## 6. Free-form design (`layout: "freeform"`)

The ten fixed layouts are fine for plain content. When the user wants a designed deck (a cover with impact, a
process diagram, a timeline, a comparison, a picture-led slide), use `freeform`: you place every element yourself.
You are the designer, so design on purpose, and let `build_presentation`'s warnings and `preview_presentation` be
your critic.

**Charts (the `chart` layout and freeform `chart` elements take the same options).** `kind`: `column`, `bar`, `line`, `area`, `pie`,
`donut`, `stacked_column`, `stacked_bar`, `stacked_area`, `scatter` (series with `points` as [x, y] pairs). A **combination chart**
is `kind: "column"` with some series set to `"kind": "line"` and, when the scales differ, `"axis": "secondary"` (with
`y2_title` and `y2_number_format`). Options, all optional: `title`, `x_title`, `y_title`, `number_format` (Excel style: `0%`,
`#,##0`, `$#,##0.0`), `data_labels` (default: on for one series, pie and donut; off otherwise), `legend` (`auto`, `none`,
`bottom`, `right`, `top`), `colors` (one per series), `point_colors` (one per category, single series), `gridlines`, `y_min`,
`y_max`, `smooth`, `gap_width`. **Data from a file:** `"data_file": "data/sales.csv"` (or `.xlsx`): the first column is the
categories and every other numeric column a series; do not retype numbers you have in a file. Keep pies to 6 slices or fewer, use
one colour for one idea, label the unit on an axis, and let the slide title state what the chart shows.

**Diagrams from a recipe.** Instead of placing boxes yourself: `{"type": "diagram", "recipe": "process", "x": 0.8, "y": 2.2, "w": 11.7,
"h": 3.2, "items": ["Plan", "Build", "Ship"]}`. Recipes: `process` (2 to 6 steps with arrows), `cycle` (3 to 8, optional `center` label),
`hierarchy` (one root with nested `children`), `matrix` (exactly 4 items: top left, top right, bottom left, bottom right; `x_label`,
`y_label`, `highlight` 1 to 4), `timeline` (items with `date`, `title`, `text`), `funnel` (2 to 6 stages), `roadmap` (phases with
`items` lists). Items are strings or `{"title": ..., "text": ...}`; `color` sets the emphasis colour; `id` sets the prefix of the
generated ids. The result is ordinary editable elements. **Connectors that stay attached:** give shapes an `id`, then
`{"type": "line", "start": {"id": "a", "side": "right"}, "end": {"id": "b", "side": "left"}, "arrow": true}` (add `"kind": "elbow"` for a
stepped line, best between left and right sides); draw the line after both shapes. **Group** shapes so they move together:
`{"type": "group", "ids": ["a", "b"]}`. **Align and distribute** by id: `{"type": "align", "ids": [...], "to": "top"}`
(left, center, right, top, middle, bottom) and `{"type": "distribute", "ids": [...], "axis": "horizontal"}` (three or more, equal gaps).

**Tables (the `table` layout and freeform `table` elements take the same options).** Cells are plain values or objects:
`{"text": "Total", "bold": true, "fill": "surface", "align": "right", "colspan": 2, "rowspan": 2, "color": "accent", "size": 18}`; a merged
cell counts as several columns in its row. Table options: `col_widths` (relative, one per column), `align` (per column; default
numbers right and text left), `formats` (one number format per column: `#,##0`, `0.0%`, `$#,##0.00`), `style` (`striped`, `plain`,
`lines` for horizontal rules, `grid`), `header_fill`, `first_column_bold`, `size`, and `heatmap` (`{"columns": ["Revenue"], "low":
"background", "high": "accent"}` shades each numeric column by its own range; text colour follows the shade). A long table on the
`table` layout takes `split_rows: 8` to continue on further slides with the header repeated; the first slide keeps the notes. Keep
tables to what the audience must read exactly; if the point is a trend, use a chart.

**Icons.** `find_icon("growth chart")` lists icon names (Lucide outline icons and Material filled icons, bundled, offline). In a freeform
slide: `{"type": "icon", "name": "lucide:trending-up", "x": 1, "y": 2, "w": 0.8, "h": 0.8, "color": "accent"}`; the box must be square.
Put an icon in a coloured circle with `"badge": "accent"` and a white icon (`"color": "#FFFFFF"`, `"badge_shape": "rounded"` for a
square). They are real shapes: recolour them in PowerPoint like any shape. `weight` (0.5 to 2.5) thins or thickens outline icons;
use about 0.6 to 0.8 above 1.5 in so they do not look heavy. One icon style per deck; icons beside text, not as decoration.

**Depth and polish.** Text and shape elements take `fill_to` (a second colour: a linear gradient; `gradient_angle` 0 is left to right,
90 top to bottom), `opacity` (0 to 1) and `shadow` (`soft`, `lifted`, `hard`). Pictures take `frame` (`rounded` or `circle`; a circle
needs a square box) and `shadow`. A slide takes `background_to` (gradient background), or `background_image` with `scrim` (0.4 to
0.7 lays the background colour over the picture so text stays readable). Use them sparingly: one gradient or shadow idea per
deck, consistent everywhere. The build judges text contrast against the worst end of a gradient and against a transparent fill
as it really looks, and warns about text over a picture with no scrim.

**Rich text in one line.** Set `"rich": true` on a text element to mix styles inside a line: `**bold**`, `*italic*`,
`[link text](https://...)` and `{accent}coloured words{/}` (theme colour names accent, text, muted, surface, or `#RRGGBB`).
Use it to emphasise a figure inside a sentence ("Revenue grew **42%** in Q3"), not to decorate. Also available on text
elements: `line_spacing` (a multiple, 0.8 to 3), `letter_spacing` (points; a little positive spacing suits small capitals)
and `vertical` (`up` or `down`) for a turned label.

**Containers instead of arithmetic.** Put elements in a `row`, `column` or `grid` and let the builder compute the
coordinates: `{"type": "row", "x": 0.8, "y": 2.2, "w": 11.7, "h": 3.2, "gap": 0.4, "children": [card, card, card]}` gives
three equal cards. Children are ordinary elements without x, y, w and h. Optional on a child: `weight` (share of the free
space, default 1), `length` (fixed inches along the direction), `cross` (fixed inches across it; the container's `align`
start, center or end places it), `colspan` (grid only). A grid has `cols`; children fill it row by row. Containers nest
(a row of a text column and a picture). Use them for cards, timelines, comparisons and stat rows; fewer collisions, easier to
change.

**The canvas** is 13.333 x 7.5 inches; positions and sizes are in inches, origin top-left. Elements are drawn in
list order (first = back). Keep 0.8 in side margins and 0.5 in top/bottom for text; only full-bleed shapes and
pictures go to the edge. Every slide still has a `title` (for navigation and screen readers). It is shown at
`title_box` (default top-left, 34 pt); set `title_visible: false` when the design makes the headline part of the
artwork (a cover), and put the real headline in a text element.

**Elements:** `text` (size, bold, color, align, valign, optional `fill`/`line`/`rounded` to make a card,
`bullets`, `font`: title/body/mono; text shrinks to fit its box down to `min_size`), `shape` (rect, rounded,
oval, triangle, diamond, chevron, pentagon, arrow_right, plus; `text` inside; `rotate`), `line` (x1,y1 to x2,y2,
`arrow`, `dash`), `image` (`fit`: contain or cover, `alt` required), `chart`, `table`.
**Colours:** use theme names so the deck stays consistent and readable in all three themes: `text`, `muted`,
`accent`, `accent_text` (text on an accent fill), `surface` (card background), `background`, `series1`..`series6`
(the chart palette). Use `#RRGGBB` only for a brand colour the user gave you.

**Design rules**
- **One focal point per slide**, and a clear reading order (top-left to bottom-right). The most important thing
  is the biggest: 44-72 pt for a hero line, 28-36 for a headline, 18-24 for body, 14-16 for captions, never
  below 12. Use at most two sizes of body text on a slide.
- **A grid, not a scatter.** Pick 2-4 columns and align left edges and tops. Equal gaps (0.3-0.5 in) between
  siblings, equal widths for equal things. Whitespace is a feature: leave a third of the slide empty.
- **Colour with purpose:** `accent` for the one thing to look at, `muted` for secondary text, `surface` for
  cards. Do not rainbow: one accent plus one `series` colour is plenty. Text on a coloured fill: use
  `accent_text` for `accent`, and `text` (dark) on the lighter `series` colours; the builder warns on low contrast.
- **Show structure with shape, not words:** numbers in circles, steps as chevrons joined by arrows, comparisons
  as two cards, a timeline as a line with dots. Keep words in diagrams to a few per node.
- **Never overlap by accident.** A card (a `fill`ed text element or a shape) may contain text on top of it;
  nothing else should collide.

**Recipes** (change the words and sizes, keep the proportions)
- *Cover:* background shape `rect` x0 y0 w0.35 h7.5 `accent`; headline text x1.1 y1.3 w8 h2.9 size 64-72 bold
  `font:"title"` valign middle; subtitle x1.1 y4.4 w7 size 24 `muted`; a number or badge in an `oval`
  (x9.6 y1.5 w3.2 h3.2, `fill:"series2"`, text `color:"text"`, size 40 bold); `title_visible:false`.
- *Three steps:* three `chevron` shapes y2.4 h1.5 at x0.8, 4.8, 8.8, w3.8 (`accent`, `series2`, `series3`) with
  `1  Plan` labels (22 pt bold; `color:"text"` on series fills), and under each a `text` card (`fill:"surface"`,
  `rounded:true`) at y4.3 w3.6 h1.8, size 20.
- *Comparison:* two `text` cards x0.8 and x6.9, y2.2, w5.6, h4: the first line a bold heading (a separate
  small text element above in `accent`), the rest short lines with `bullets:true`.
- *Big number:* one huge text (size 96, `accent`, bold) at the left third, and a short explanation at the right
  two thirds (size 24) aligned to its vertical centre.
- *Timeline:* a `line` x0.8 y3.8 to x12.5 y3.8 (width 3); an `oval` (w0.4) on it per event; the date above (bold,
  18 pt) and a 16-18 pt note below, alternating nothing: keep all labels on the same sides.
- *Picture-led:* an `image` with `fit:"cover"` over the whole slide (x0 y0 w13.333 h7.5) and a `text` card
  (`fill:"background"`, `rounded:true`) on top for the words, so they stay readable.

After building, **look**: preview, then check every slide for balance, alignment, crowding and reading order
before you call it done. Fix by changing the numbers and rebuilding; that is cheap.

## Gotchas
- Dense bullet lists were the top complaint in every deck benchmark: choose `cards`, `steps`, `stats`, a chart or a diagram first.
- The build warnings are not optional: fix them and build again (a template deck that ignored them lost its numbers).
- A new slide in an edited deck lands before the closing slide by itself: do not add `move_slide`.
