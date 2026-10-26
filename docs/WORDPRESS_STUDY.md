# What to take from WordPress (TODO TH7, TH8)

A study of two public things, read as a person reads them, to decide what DebCraft's office screens and brand layouts still lack. Same
verdicts as `docs/SKILLS_STUDY.md`: **take** (build it), **adapt** (build a version that fits our style), **skip**. Facts and ideas only; no
code, text or pictures are copied (`docs/THEME_CLEAN_ROOM.md`). This is written from the behaviour of the WordPress admin and the public
pattern directory as they are documented; it has not been checked against a live site from the build machine, so each "new screen" below
is a proposal to confirm against the user's own admin before it is built.

## TH7 — admin patterns (office screens)

| Pattern in the WordPress admin | What it is for | Verdict | What we build |
|---|---|---|---|
| **Status links with counts** above a list ("All (42) \| Published (30) \| Draft (8) \| Trash (4)") | One click filters the list; the counts tell the state of the work at a glance | take | Already close to our tab row with count chips (`app-grouped-tasks`, `app-approval-queue`); add it as the standard header of every list screen |
| **Row actions on hover** (Edit \| Quick Edit \| Trash under the title) | Keeps the row clean; the actions appear when needed | adapt | On touch screens there is no hover: show them always on phones and on keyboard focus (a rule for the office polish recipe) |
| **Bulk actions** (checkboxes, a select of actions, Apply) | Act on many rows | take | A selection bar that appears when a row is ticked ("3 selected: Approve, Reassign, Delete"); our tables have checkboxes but no bar |
| **Dismissible notices** (success, warning, error at the top, with a close) | Feedback that does not block | adapt | A toast plus an inline banner; ties to the existing empty/error states |
| **Screen options** (choose columns, rows per page) | Per-user list tailoring | adapt | A "Columns" menu on tables and a page-size select; stored per user |
| **Quick edit** (inline edit of a few fields in the row) | Fast fixes without leaving the list | adapt | Our slide-over drawer form (`app-drawer-form`) is the better fit; add inline edit for one or two fields |
| **List views that switch between table, grid and list** (media library, newer admin views) | The same data seen as rows or cards | take | A view switch on the project list that toggles `app-card-grid` and the table; new screen "collection with a view switch" |
| **Settings page with sections and one Save** | Many options, one commit | skip | We have grouped settings with per-section save, which is clearer |
| **Dashboard widgets that can be dragged and hidden** | Customisable home | skip for now | High effort, low value for the first office apps |

New screens proposed from this table (office style, our own code): *list with status links, bulk bar and column menu*, *collection with a
table/grid view switch*. Neither is built yet; they would be `BO10` and `BO11` once the user confirms the list.

## TH8 — block patterns and theme directory as a section taxonomy

The public pattern directory groups patterns by purpose. Used here only as a list of **section kinds** (not their markup), to decide which
brand layouts DebCraft lacks for `BO9`.

| Section kind | Variants worth having | Our state |
|---|---|---|
| Hero | text + image split; full-bleed image with overlay text; centred headline with one button; product screenshot below | 8 `lay-` compositions cover split, poster and full-bleed; centred and screenshot variants missing |
| Features / services | three icon columns; alternating image rows; numbered steps; bento grid | three-column and bento exist; alternating rows and steps missing |
| Pricing | three tiers with one highlighted; comparison table; single plan | tiers exist in a template; comparison table missing |
| Testimonials | one large quote; three cards; logo wall | partly |
| FAQ | accordion; two-column list | accordion only |
| Team / people | photo grid; list with roles | missing |
| Gallery / portfolio | masonry; uniform grid; case-study cards | uniform grid only |
| Contact / location | form + map; address cards | form only |
| Call to action | banner; split with image | banner |
| Footer | simple; multi-column with newsletter | simple |
| Events / menu / courses | list with date or price column | missing (subject-specific) |

**Licence check before relying on any pattern:** the pattern directory's patterns are published under GPL-compatible terms (many GPL-2.0+,
some CC0). We do not copy their markup; we write our own sections for the kinds above, so the licence does not attach to our output. Record
this decision in `docs/DECISIONS.md` when `BO9` starts.

**Recommended order for `BO9`:** subjects first (wellness, local services, events, portfolios, SaaS, non-profit, education, hospitality,
as the user asked), each with colour slots and a drawn scene; add the missing section kinds (team, steps, comparison table, centred hero)
as shared parts.
