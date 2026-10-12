# Asset standard

Every ready-made piece (visual direction, effect, component, later templates, sections, font pairings, coding recipes) is
one file `assets/<type>/<id>.md` with front-matter and a usage note. `scripts/build_asset_catalogue.py` validates them and
generates `catalogue.json`, `INDEX.md` and `LICENSES.md` (never edit those by hand). The model finds assets with
`find_asset` and brings one in with `add_asset`; both read `catalogue.json`.

Required front-matter: `id` (lowercase, hyphens, equals the file name), `type` (one of the types in
`forge/parity/assets.py`, equals the folder name), `title`, `summary` (one line), `licence`, `source`, `tested` (how it was
verified). Optional: `moods`, `products`, `tags`, `density` (airy, balanced, dense, any), `dependencies` (packages to
install), `files` (a list of `{from, to}`: files inside this skill folder copied to a path inside the project), `preview`
(an image path, a warning until the previews are generated).

Acceptance bar for every new asset (TODO L12): built with Vite + Tailwind v4, audit clean at 1280 and 375 px, screenshot
reviewed, licence recorded, a usage note, and a retrieval prompt in `tests/test_assets.py` that finds it. Third-party code is
not vendored (D-255); write in our own words and record the licence of anything derived.
