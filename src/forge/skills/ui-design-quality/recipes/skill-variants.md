# 6. Several variants of one page (three designs, A/B, "options")
Variants that look the same are a failed task, however polished each one is.
- Build the variants at the same time, not one after another: call `build_variants` with the shared requirement and, per variant, a name, its own folder and its direction (the one-line brief you wrote for it). Each builder writes its own DESIGN.md in its folder and builds from its tokens, so the variants cannot share a stylesheet. Then verify each variant yourself, run `compare_designs` and have the whole reviewed once.
- Write a one-line design brief per variant first (palette, fonts, layout idea, mood) and make them differ on all of
  them: for example light and warm with a serif heading, dark and loud with huge type, clean product style with
  cards. Different colours on the same layout do not count.
- Build each variant in its OWN folder, from scratch (do not copy one project over another), with its own port and its
  own `<title>` (for example "Eureka - Design A").
- Prove each port serves its own folder: read the title and heading from `browser_open` for every port, and compare the
  screenshots (each `view_image` prints a sha256; identical hashes mean identical pages) or hash the source files
  (`Get-FileHash designs\*\src\App.tsx`). If two match, fix it before you report.
- Then run `compare_designs` with one screenshot per variant (and each variant's folder, so the DESIGN.md files are compared too): it
  reports the layout similarity of every pair. A pair marked TOO SIMILAR, or two DESIGN.md files naming the same first colour or font, is a
  BLOCKER: change the layout (section order, grid, hero shape) and the typeface of the later variant, not just its colours.
- Start each server with `start_background` and its own `cwd` (for example `cwd: designs/design-a`; without it the
  process starts wherever an earlier `cd` left the shell and several servers end up serving one app). Check the
  `[cwd: ...]` in the result, then `show_app` per server. If
  `show_app` fails, read its message and fix the cause (it tries 127.0.0.1, localhost and [::1]); do not hand the
  user commands to run instead of running them yourself.
