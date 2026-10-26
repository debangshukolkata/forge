# Clean-room rules for theme inspiration (TODO TH1..TH5, D-491, D-492)

DebCraft can take a theme the user likes (a WordPress theme, a GitHub theme repository, a demo address) as inspiration and write its own
page. This is the protocol that keeps the result an original work.

## The rules
1. **What we read:** public pages, public APIs (the WordPress.org and WordPress.com theme lists, the GitHub API) and public repositories,
   the way a person would read them. Only through the web address guard. Never a clone into the project; files are read into memory.
2. **What we keep:** facts, in our own words, in `.forge/inspiration/<slug>.md`: colours, font names, sizes, widths, shadows, the order of
   sections, how many columns and pictures each has, and the licence. A draft DESIGN.md of those values.
3. **What we never keep or use:** code, text (including headings and descriptions), pictures, icons, logos, the theme's name or author in
   the output. A pixel-for-pixel clone is not made either: the page must have its own Concept (D-486).
4. **GPL themes:** most WordPress themes are GPL. A page that copies GPL code and changes a little is a derivative, so nothing is copied
   to begin with. Dawn (Shopify) is MIT; the licence is recorded anyway.
5. **The check:** `theme_search study` stores a fingerprint of the studied files (hashes of 16-token runs, never the text). `theme_search
   check` compares every HTML, CSS and script file of the project with it and fails a file that shares a run of about 21 tokens or 5 % of
   its runs. The model rewrites the file; it does not tweak copied lines. The existing "too close" fingerprint check of designs applies too.
6. **Provenance:** one line per theme in `.forge/inspiration/LOG.md` (name, address, licence, "facts only"). When the user asks for an
   exact copy of a paid or licensed theme, DebCraft says no and offers an inspired original.
7. **The user decides:** after the study, one question shows what was learned (palette, fonts, section order); the user can keep some and
   change others before anything is built.

## What the check can and cannot show
- It finds copied code and copied wording. It does not judge whether a layout is "too similar in spirit"; that is the Concept step and the
  user's eyes.
- Short boilerplate (a CSS reset, a viewport meta) is shorter than the run length and is not flagged.
- Colours and font names are facts and may match.
