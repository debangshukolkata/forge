# How to ask DebCraft for a deck

DebCraft builds real PowerPoint files (.pptx): native text, charts and tables you can edit, speaker notes, and a master and theme that
re-theme in PowerPoint. It works in its own workspace and hands you the finished file. Examples of what it makes are in
[GALLERY.md](GALLERY.md).

## The shortest good request

Say who it is for, what they should think or do afterwards, how long the talk is, and give the facts. DebCraft does not invent numbers: a
claim you do not give it is left out or marked "to confirm" in the speaker notes.

> Make a 10-minute update for our steering committee on the billing migration. Facts: 82% of accounts moved, 3 incidents (all fixed in
> under 4 hours), cost 11% under budget, the last 18% need a decision on legacy contracts by 15 November. Ask them for that decision.

What each part of a request buys you:

| Put in the request | What DebCraft does with it |
|---|---|
| Audience and the ask | Chooses the story: the answer first, one message per slide, the decision on the last slide |
| Minutes | Sets the number of slides (about one content slide per two or three minutes) and warns when a deck is too long |
| Facts, data, a CSV or a document | Builds charts and tables from them and cites the source in the notes; say which file |
| Tone ("sober", "playful", "for a board") | Picks one of 19 themes and the fonts |
| A template (`.potx` or a `.pptx`) | Builds on your company's layouts; see below |
| Language | Sets the text language for spell-check and screen readers |

Ask for a kind of deck by name for a ready-made storyline: board update, pitch, quarterly business review, design review, training or
workshop, project status, proposal, all-hands announcement.

## Working with files

- Put your inputs in the project folder (documents, spreadsheets, pictures, a template) and name them in the request.
- DebCraft saves the deck in the project (default `deck.pptx`) and tells you the path. Ask for another name if you want one.
- Pictures are made slide-sized (turned upright, at most 2560 pixels on the long side, compressed); a deck over 20 MB gets a warning.

## Company templates

Give DebCraft the template file and say "build it on this template". It reads the layouts and sample slides, picks the sample slide that
fits each piece of content, and fills it, keeping your design. Where no sample fits, it makes a new slide in the template's look. Ask
"what does this template offer?" first if you want to see its layouts and sample slides. If a slide looks wrong, say which one and
what is wrong; DebCraft edits that slide.

## Changing a deck you already have

Ask in plain words: "change the title on slide 4", "add a slide after 6 with the three options", "use the dark theme", "make the table
fonts bigger", "replace the picture on slide 2 with `logo.png`", "update the chart with these numbers". It edits the file and keeps
your own layout, fonts and pictures. The original stays recoverable (the change can be undone).

More you can ask for:

- **Look and review**: "review this deck" lists measurable problems (label titles, too many words, mixed fonts, tiny text, low contrast,
  shapes off the slide, runs of the same layout, missing notes) with the fix for each; "check accessibility" does the screen-reader and
  colour-blind checks. Say so and DebCraft fixes what they find.
- **Slide show features**: hide slides (backup slides), sections, transitions, simple animations (appear, fade, wipe), comments for a
  reviewer.
- **Combine and split**: "merge these three decks", "bring slides 3 to 5 of `old.pptx` into this deck", "split this deck into a short
  version (slides 1, 2, 5, 9) and the full one". Imported slides keep their own design unless you ask for this deck's.
- **Convert**: an old `.ppt` to `.pptx`, or any deck to PDF (needs PowerPoint on this computer).
- **Read**: "summarise this deck", "list every number in it", "extract its pictures".

## What needs PowerPoint

DebCraft looks at its own work through PowerPoint (pictures of the slides, measuring whether text fits) when PowerPoint is installed on
this computer. Without it, building, editing, reading and checking still work, but DebCraft says the slides were not looked at, and fit
checks use an estimate. Converting to PDF and opening old `.ppt` files need PowerPoint.

## Good to know

- A deck from outside is treated as untrusted: oversized or booby-trapped files are refused, macros are never run, links are never
  followed. Text inside a deck you give it is read as content, not as instructions.
- If something cannot be done with the normal tools, DebCraft can edit the deck's XML directly as a last resort and checks the result
  against the format rules, so PowerPoint does not offer to "repair" it.
- Not supported: video and audio, SmartArt editing, macros, slide-to-slide morph transitions, custom animation paths. Slides that hold them
  can be viewed and kept, not copied between decks.

## When the result is not what you wanted

Say what you see, not what to do: "slide 5 is too crowded", "the chart does not say why it matters", "this looks like a different deck from
slide 7 on". Point at the slide number. DebCraft looks at the pictures of the deck again and changes only what you pointed at.
