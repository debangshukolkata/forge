# Reference decks (D-399)

Decision of 2026-10-15 (user): the user will not supply sample decks or templates; DebCraft's presentation work is checked against decks collected from the web.

## What is collected, where, and under which licence

`python scripts/dev/fetch_reference_decks.py` makes shallow sparse clones into `C:\Work\ForgeSamples\reference-decks\_src` (outside this repository, so nothing is redistributed):

| Source | Licence | Files | Good for |
|---|---|---|---|
| Apache POI `test-data/slideshow` | Apache-2.0 | about 100 `.pptx`, `.potx`, `.ppsx`, `.thmx` (plus legacy `.ppt`) | odd real-world structure: many masters, layouts, themes, charts, tables, embedded objects, other languages |
| python-pptx `tests/test_files`, `features/steps/test_files` | MIT | about 66 | clean files from several PowerPoint versions, placeholders, pictures, charts |
| LibreOffice core `sd/qa/unit/data/pptx`, `oox/qa/unit/data` | MPL-2.0 | about 500 | regression files for import bugs: SmartArt, gradients, text effects, tables, shapes, animations |

## What is not collected, and why

Designed marketing templates (Slidesgo, SlidesCarnival, SlideModel, Microsoft's own templates, Envato) are all under terms that allow use in a presentation but not copying or machine reading into a test set, and several require attribution or forbid redistribution. They are not downloaded. A deck the user wants matched is brought by the user; the match-a-deck tools (`describe_design`, template mode) work on whatever file is given.
Open government sources (NASA/JPL, the City of Philadelphia, the Indian government portal) were checked on 2026-10-15: no `.pptx` under a clear open licence was found, and the Indian portal limits downloads to officials.

## How they are used

`python scripts/dev/reference_deck_sweep.py C:\Work\ForgeSamples\reference-decks\_src --out sweep.md` opens every file with python-pptx and runs the template reader, the design reader and the sample reader, and lists every failure with its source line: a robustness test for the readers on files nobody wrote for us. The results and the fixes are in the DECISIONS entry D-399.

## First sweep (2026-10-15)

670 files (Apache POI 100, python-pptx 66, LibreOffice 504): 646 opened with python-pptx and ran through the template reader, the design reader and the sample reader. 24 did not open: deliberately corrupt fuzzer files (bad zip, bad CRC), strict-OOXML and password-protected files, `.ppsx` files that python-pptx rejects, and two packages with a media file that has no content type; they are python-pptx's limits, not ours. One real finding in our readers: `tdf169781.pptx` has a slide master that lists a layout missing from the file, and both readers died with a bare `KeyError`; they now raise a `BuildError` that says the deck is damaged and what to do (D-399, test in tests/test_slides_template.py). Everything else, about 640 real decks, read without an error; the slowest file took 2.9 s.
