---
id: sec-form-login
type: section
title: Sign-in form
summary: "A narrow form: e-mail, password with a show and hide button, remember me, a forgotten-password link and one button."
moods: [plain, trustworthy, focused]
products: [app, account, members area, saas, portal]
tags: [react, tailwind v4, tokens only, form, login, sign in, password, validation]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-form-login.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FormLogin.tsx
    to: src/sections/FormLogin.tsx
---

## Sign-in form

Component `FormLogin` in `src/sections/FormLogin.tsx`. Every prop has a default (example content): pass your own words and links. `onSubmit(credentials)` may be async and return an error text to show above the fields. Wire it to the real back end; never keep the password in state longer than the submit. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
