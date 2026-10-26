# Back-office polish: what makes an office app look finished (D-489)

Use this for tools people work in all day: approvals, queues, tables, forms, records, settings, dashboards, imports, reports. It is a set of rules and
one recipe per component, taken from a well-made office app (an orange, Inter-set constituency CRM) and written here in our own words. The design system
`ds-office-polish` (find_asset type design-system, "office") holds the tokens; the screens in `recipes/app-screens` use all of this. The look does not come
from decoration. It comes from **one accent, one recipe per component and no exceptions**.

## The rules
1. **One accent.** Orange marks the main action, the active menu item, the tab underline and the counts. Everything else is neutral. A second hue appears
   only as a status (green, amber, red, blue).
2. **One recipe for every coloured label.** A badge, tag, status pill or icon chip is: a pale tint of the colour as the background, a darker text of the same
   hue, and a 1px inner ring of the same hue at about 20 percent. Never a solid colour block, never colour as the only signal (the label says it in words).
3. **Layers, not borders and shadows everywhere.** Page: cool off-white. Cards: white, 1px light border, one soft shadow (`0 1px 2px` and `0 6px 20px`, 5 to 6
   percent black). A card you can click lifts 2px on hover and gets a deeper shadow. Nothing else casts a shadow.
4. **One family of corners.** Cards 16px, controls 12px, small items 8px, chips and pills fully round.
5. **Hierarchy by weight and grey, not by many sizes.** Page title 24px bold with tight tracking; section title 16px semibold; body 14px; labels 11px
   uppercase and spaced in the muted colour; figures in tabular numerals. Four or five sizes in the whole app.
6. **Even, generous spacing.** Card padding 20px, gaps 16px, page margin 32px on a desktop, one left edge per column.
7. **Icons: one family, one stroke.** On their own (stat tile, page header, empty state) an icon sits in a 44px rounded square with the same tint and ring.
8. **Motion is small and quick (200 to 300 ms):** fade and rise on mount (50ms apart for a row of tiles), lift on hover, 98 percent scale on press, a sliding
   tab underline, a spring for a drawer. Respect `prefers-reduced-motion`. Nothing bounces for show.
9. **Real states.** Loading is a shimmer skeleton in the shape of the content; empty is an icon chip, a title and one action; an error says what to do.
10. **Local conventions.** Money and dates in the reader's own convention (lakh and crore, 30 Sep 2026); numbers right-aligned and tabular.

## The recipes (plain HTML kit classes, then Tailwind)
- **Status chip.** HTML: `.pill.pill--ok|warn|danger|info`. Tailwind: `bg-{c}-50 text-{c}-700 ring-1 ring-inset ring-{c}-100 rounded-full px-2.5 py-0.5 text-xs font-semibold`.
  Check the contrast of the text on its tint (4.5 to 1); if the 700 shade fails, use 800.
- **Stat tile.** HTML: `.card.card--lift.kpi > .tile > (label + figure) + .chip` and a `.foot` line. Tailwind: `rounded-xl border bg-card p-5 shadow-card hover:-translate-y-0.5
  hover:shadow-card-hover`, the chip `h-11 w-11 rounded-xl bg-{c}-50 text-{c}-700 ring-1 ring-inset ring-{c}-100`.
- **Button.** Primary: filled with the deep accent, white text, `shadow-sm`, `active:scale-[0.98]`, a 2px focus ring with a 2px offset. Secondary: white,
  1px border, a pale accent tint on hover. Ghost: grey text, grey tint on hover. Heights 32 / 40 / 44.
- **Field.** 44px high, 12px corners, 1px border, `shadow-sm`; focus: accent border and a soft 4px ring (`ring-4 ring-primary/20`); error: red border and ring plus a
  12px message below.
- **Tabs.** Text tabs on a 1px rule; the active tab in the accent colour with a 2px underline that slides; a count badge (grey, accent when active).
- **Table.** Header row on a pale grey, 12px uppercase labels; rows divided by a 1px line; the hover and selected row take the pale accent tint; an overdue row
  carries a 3px red bar on its left edge (`.row-alert`).
- **Page header.** Breadcrumb, then a 44px icon chip, the title, one muted line, and the actions on the right.
- **Drawer.** From the right, 576px wide, dark scrim with blur, spring in, header with title and description, a close button and optionally an expand-to-full-screen
  button, a scrolling body, a sticky footer on a pale grey with Cancel and the main action; Escape closes it.
- **Tree.** One coloured dot per depth (a different hue for each of the first levels), a chevron that rotates, row actions that appear on hover (only where the
  device can hover), the selected row on the pale accent tint with a ring.
- **Shell.** White side menu with grouped, small uppercase labels; the active item a pale accent tint, semibold, with a count badge in red for what needs
  attention; a sticky top bar that blurs the page behind it, a search box showing its keyboard shortcut, one Quick Add button, the theme toggle, notifications
  and the user.

## Accessibility notes
- White text on bright orange (`#FF7A00`) is only 2.6 to 1. Filled controls use the deeper orange (`primary`, `#A34C00`, white text 5.9 to 1); the bright orange
  (`brand`) is for the menu bar, the underline, progress, the focus ring and icon tints, never for text on white.
- Muted text must stay 4.5 to 1 on every surface it sits on, including the tinted ones (use `#5F6672`, not `#6B7280`, on a grey tint).
- Dark mode is a second set of tokens, not a list of overrides for white and slate.
