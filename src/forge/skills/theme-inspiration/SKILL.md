---
name: theme-inspiration
description: Use when the user likes a theme, template or site and wants a page or app that feels like it (a WordPress theme name or link, a GitHub theme repository, a demo address, or only a look such as "a minimal portfolio theme"): find it, study it read-only, show what was learned, then write an original page that shares no code with it
---

# Theme inspiration

The user gives a look, a theme name or a link. You study it the way a person looks at a public page, keep the facts, and write your own
page from our design system. The theme is a reference, never a source of code, words or pictures.

## 1. Find it
- A look in words ("minimal portfolio"): `theme_search` action `search`. It reads the public lists (WordPress.org, WordPress.com, GitHub)
  and saves screenshots. Show up to **four** in ONE `ask_user` question (name, one line of what it looks like, the picture). The user can
  ask for more or type another name or link.
- A theme name or a link (`wordpress.com/theme/solarone`, a GitHub address): skip the search and study it.
- A plain demo address, or a site that is not a theme: `design_inspire` reads it (screenshot, computed styles, section structure).
- Other theme systems (Ghost, Hugo, Jekyll, Shopify Dawn, HTML templates) have no special tool: work from the user's link, a general web
  search for "<kind> theme" and the demo, and say plainly what could not be read.

## 2. Study it (read-only)
- `theme_search` action `study` with `owner/name`, a repository address or a WordPress.org theme name. It reads `theme.json`, `style.css`,
  `patterns/`, `templates/` and `parts/` into memory and writes only facts to `.forge/inspiration/<slug>.md`: colours, font names, sizes,
  content and wide widths, shadows, the licence, and for each section how many columns, headings and pictures it has. It also writes a
  draft design system `<slug>.DESIGN.md` and a fingerprint (hashes, no text) for the later check.
- If a link cannot be read (a private repository, a paid theme with no public files), say so and work from the demo with `design_inspire`.
- A request for an **exact copy** of a paid or licensed theme gets a plain answer: we do not copy a theme; we can build an original page
  with the same feel. Offer that.

## 3. Show what you learned, then build
- Before building, tell the user in ONE `ask_user` question what you learned (palette, fonts, section order) and let them say "keep the
  colours, change the layout". Their answer wins.
- Write the page from **our** `DESIGN.md` (start from the draft, adapt it to the product), the closest of our compositions, our own markup,
  our own words and drawings, and fonts from `find_font`. Fix the section order and proportions you learned; change everything else.
- Never copy a line of code, a text, a picture or a logo. Never put the theme's name, author or logo in the page. Do not paste its CSS
  and "change a few values": a small change to copied code is still a copy.
- The Concept step still applies: the page needs its own idea, not only a different skin on the theme's structure.

## 4. Prove it
- When the page is built, call `theme_search` action `check`. If it says TOO CLOSE, rewrite those parts (different markup and class names,
  own words); do not nudge the copied lines.
- Run the fingerprint ("too close") check against the studied design as for any inspiration.
- Tell the user the theme's licence and where it came from (it is in the note and in `.forge/inspiration/LOG.md`, one line per theme).

## Rules
- Queries and links go through the web address guard; in Mode B a term from the host never goes into a search.
- Facts (colours, font names, sizes, proportions, section order) are free to use; expression (code, text, pictures, logos) is not.
- Full protocol: `docs/THEME_CLEAN_ROOM.md`.
