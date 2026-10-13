# Trying a company template on another laptop (`forge template-probe`)

For the laptop that has the corporate PowerPoint template and DebCraft installed (Windows with PowerPoint gives the pictures; without it
you still get the report and the test deck).

```
forge template-probe "C:\path\to\company-template.potx"
```
Add `--hide-text` to leave the words of the template's slides out of the report, `--out <folder>` to choose where the files go
(default: next to the template, in `<template name>-probe`).

What it writes (in the folder it prints):
- `report.txt` - how DebCraft reads the template: size, theme colours, fonts, the layouts and sample slides (each with its kind and
  slots), a list of "things to look at", and PowerPoint's measurement of text that does not fit.
- `probe-deck.pptx` - a deck built on the template with placeholder text: every sample slide once with normal text and once with long
  text, each ordinary layout, a chart, a table and a diagram. Open it in PowerPoint and look: every slide should look like the
  template's own work.
- `template-contact-sheet-*.png` and `probe-deck-contact-sheet-*.png` - pictures of the template's slides and of the probe deck, and the
  single pictures in `template-pictures/` and `probe-deck-pictures/`.
- `probe.json` - the same findings as data.

What to send back: `report.txt` and the contact sheets (`*-contact-sheet-*.png`). The pictures show the template, so check them before
sending; with `--hide-text` the report has no template wording, but the pictures still do. Nothing is sent anywhere by the command.
