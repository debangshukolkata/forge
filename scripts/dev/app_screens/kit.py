"""Shared pieces of the application-screen recipes (D-366): palettes, the icon sprite, the base stylesheet and small chart builders.

Every recipe is written out as one standalone HTML file (no build step, no external requests): the :root block holds the tokens that
`design_md_export css-variables` produces for a real project, so the model replaces that block and keeps the rest."""

from __future__ import annotations

# The token names match the exported DESIGN.md variables used by the marketing compositions (neutral, ink, muted, primary, accent2, border).
PALETTES: dict[str, dict[str, str]] = {
    "slate": {  # cool light, one blue: the plain product look
        "neutral": "#f4f5f7",
        "surface": "#ffffff",
        "ink": "#151a22",
        "muted": "#586273",
        "primary": "#2352c8",
        "on-primary": "#ffffff",
        "accent2": "#b4530c",
        "border": "#dde1e8",
        "ok": "#12683f",
        "warn": "#8a5200",
        "danger": "#b42318",
    },
    "paper": {  # warm light, green and terracotta
        "neutral": "#f5f0e7",
        "surface": "#fffdf9",
        "ink": "#241e17",
        "muted": "#675b4e",
        "primary": "#1e6b58",
        "on-primary": "#ffffff",
        "accent2": "#a8481b",
        "border": "#ddd3c3",
        "ok": "#1b6a3a",
        "warn": "#8a5300",
        "danger": "#b3261e",
    },
    "ink": {  # dark, one cool accent
        "neutral": "#0e1116",
        "surface": "#161b22",
        "ink": "#edf0f5",
        "muted": "#9aa5b4",
        "primary": "#6aa6ff",
        "on-primary": "#07101f",
        "accent2": "#f0a35c",
        "border": "#262d37",
        "ok": "#5fd08f",
        "warn": "#f0b45a",
        "danger": "#ff8a80",
    },
    "harbour": {  # cool teal on pale blue-grey, amber for attention
        "neutral": "#edf3f4",
        "surface": "#ffffff",
        "ink": "#0e2a33",
        "muted": "#4d6670",
        "primary": "#0a6670",
        "on-primary": "#ffffff",
        "accent2": "#b8620f",
        "border": "#d3e0e3",
        "ok": "#17693d",
        "warn": "#8b5200",
        "danger": "#b3261e",
    },
    "mono": {  # near-black on white with one orange signal
        "neutral": "#fafafa",
        "surface": "#ffffff",
        "ink": "#0b0b0c",
        "muted": "#55585f",
        "primary": "#0b0b0c",
        "on-primary": "#ffffff",
        "accent2": "#c2410c",
        "border": "#e2e2e4",
        "ok": "#166534",
        "warn": "#8a4b00",
        "danger": "#b42318",
    },
}

FONTS: dict[
    str, tuple[str, str, str]
] = {  # name -> (display stack, text stack, mono stack): all bundled families (find_asset type font)
    "inter": (
        '"Inter",system-ui,sans-serif',
        '"Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
    "manrope": (
        '"Manrope","Inter",system-ui,sans-serif',
        '"Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
    "jakarta": (
        '"Plus Jakarta Sans","Inter",system-ui,sans-serif',
        '"Plus Jakarta Sans","Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
    "grotesk": (
        '"Space Grotesk","Inter",system-ui,sans-serif',
        '"Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
    "dmserif": (
        '"Fraunces","Georgia",serif',
        '"DM Sans","Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
    "archivo": (
        '"Archivo","Inter",system-ui,sans-serif',
        '"Archivo","Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
    "nunito": (
        '"Nunito","Inter",system-ui,sans-serif',
        '"Nunito","Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
    "outfit": (
        '"Outfit","Inter",system-ui,sans-serif',
        '"DM Sans","Inter",system-ui,sans-serif',
        '"JetBrains Mono",ui-monospace,monospace',
    ),
}

ICONS: dict[str, str] = {  # 24 px grid, drawn for this project: stroke icons that take the text colour
    "home": '<path d="M4 11 12 4l8 7"/><path d="M6 10v9h12v-9"/><path d="M10 19v-5h4v5"/>',
    "grid": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    "chart": '<path d="M4 20V4"/><path d="M4 20h16"/><path d="m8 15 3-4 3 2 4-6"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.4-3 2.6-5 5.5-5s5.1 2 5.5 5"/><circle cx="17" cy="9" r="2.4"/><path d="M16 14.2c2.6-.2 4.3 1.5 4.6 4.3"/>',
    "box": '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5"/><path d="M12 12v9"/>',
    "truck": '<path d="M3 6h11v9H3z"/><path d="M14 9h4l3 3v3h-7"/><circle cx="7.5" cy="17" r="1.8"/><circle cx="17" cy="17" r="1.8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "x": '<path d="m6 6 12 12M18 6 6 18"/>',
    "filter": '<path d="M4 6h16M7 12h10M10 18h4"/>',
    "calendar": '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M9 3.5v4M15 3.5v4"/>',
    "mail": '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m4 7 8 6 8-6"/>',
    "chat": '<path d="M5 5h14v10H10l-4 4v-4H5z"/>',
    "file": '<path d="M7 3.5h7l4 4V20.5H7z"/><path d="M14 3.5v4h4"/><path d="M9.5 13h5M9.5 16h5"/>',
    "card": '<rect x="3.5" y="6" width="17" height="12" rx="2"/><path d="M3.5 10.5h17M7 15h3"/>',
    "shield": '<path d="M12 3.5 19 6v5.5c0 4.2-2.8 7.2-7 9-4.2-1.8-7-4.8-7-9V6z"/><path d="m9 12 2.2 2.2L15.2 10"/>',
    "key": '<circle cx="8" cy="14" r="3.5"/><path d="m10.5 11.5 8-8M15.5 6.5l2.5 2.5M13 9l2 2"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
    "download": '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/>',
    "dots": '<circle cx="6" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18" cy="12" r="1.3"/>',
    "up": '<path d="M12 19V6M6.5 11.5 12 6l5.5 5.5"/>',
    "down": '<path d="M12 5v13M6.5 12.5 12 18l5.5-5.5"/>',
    "chevron": '<path d="m9 6 6 6-6 6"/>',
    "star": '<path d="m12 4 2.4 5 5.5.7-4 3.8 1 5.4L12 16.3 7.1 19l1-5.4-4-3.8 5.5-.7z"/>',
    "trash": '<path d="M5 7h14M10 7V4.5h4V7M7 7l1 13h8l1-13"/>',
    "edit": '<path d="M5 19l1-4 9.5-9.5 3 3L9 18z"/><path d="m13.5 7.5 3 3"/>',
    "eye": '<path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z"/><circle cx="12" cy="12" r="2.8"/>',
    "logout": '<path d="M9 4.5H5v15h4M14 8l4 4-4 4M18 12H9"/>',
    "help": '<circle cx="12" cy="12" r="8.5"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-.9.8-.9 1.4"/><circle cx="12" cy="16.8" r=".6"/>',
    "map": '<path d="m4 6 5-2 6 2 5-2v14l-5 2-6-2-5 2z"/><path d="M9 4v14M15 6v14"/>',
    "tag": '<path d="M4 4h8l8 8-8 8-8-8z"/><circle cx="8.5" cy="8.5" r="1.2"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"/>',
    "inbox": '<path d="M4 13.5 6.5 5h11L20 13.5V19H4z"/><path d="M4 13.5h5l1 2h4l1-2h5"/>',
    "send": '<path d="M20.5 3.5 3.5 10.5l6.5 2.5 2.5 6.5z"/><path d="m10 13 10.5-9.5"/>',
    "layers": '<path d="m12 4 8.5 4.5L12 13 3.5 8.5z"/><path d="m3.5 12.5 8.5 4.5 8.5-4.5M3.5 16.5 12 21l8.5-4.5"/>',
}


def sprite(names: list[str] | None = None) -> str:
    chosen = names or list(ICONS)
    body = "".join(f'<symbol id="i-{name}" viewBox="0 0 24 24">{ICONS[name]}</symbol>' for name in chosen)
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true">{body}</svg>'


def icon(name: str, extra: str = "") -> str:
    return f'<svg class="ico{" " + extra if extra else ""}" aria-hidden="true"><use href="#i-{name}"/></svg>'


BASE_CSS = """
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--color-neutral);color:var(--color-ink);font:400 15px/1.55 var(--font-body-md);-webkit-font-smoothing:antialiased}
h1{font:600 1.85rem/1.2 var(--font-display);letter-spacing:-.02em;margin:0}h2{font:600 1.05rem/1.3 var(--font-display);margin:0}h3{font:600 .95rem/1.3 var(--font-display);margin:0}p{margin:0}
button,input,select,textarea,legend{font:inherit}a{color:var(--color-primary)}:focus-visible{outline:2px solid var(--color-primary);outline-offset:2px;border-radius:4px}
.ico{width:18px;height:18px;flex:none;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.muted{color:var(--color-muted)}.mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums}.num{font-variant-numeric:tabular-nums}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
:root{--soft:color-mix(in srgb,var(--color-primary) 11%,var(--color-surface));--hover:color-mix(in srgb,var(--color-ink) 5%,var(--color-surface));--radius:14px;--r:10px;--field:color-mix(in srgb,var(--color-ink) 26%,var(--color-surface));--shadow:0 1px 2px color-mix(in srgb,var(--color-ink) 8%,transparent)}
/* shell */
.app{display:grid;grid-template-columns:240px minmax(0,1fr);min-height:100vh}
.side{background:var(--color-surface);border-right:1px solid var(--color-border);padding:18px 12px;display:flex;flex-direction:column;gap:2px;position:sticky;top:0;height:100vh;overflow:auto}
.brand{display:flex;align-items:center;gap:10px;padding:4px 10px 18px;font:700 1.05rem var(--font-display);letter-spacing:-.01em}
.brand i{width:28px;height:28px;padding:1px;border-radius:var(--r);background:var(--color-primary);color:var(--color-on-primary);display:grid;place-items:center;font-style:normal;font-size:.85rem}
.nav-title{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;color:var(--color-muted);padding:14px 10px 6px}
.nav a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:var(--r);color:var(--color-muted);text-decoration:none;font-weight:500}
.nav a:hover{background:var(--hover);color:var(--color-ink)}.nav a[aria-current=page]{background:var(--soft);color:var(--color-ink);font-weight:600}
.nav .count{margin-left:auto;font-size:.75rem;padding:1px 7px;border-radius:999px;background:var(--hover);color:var(--color-muted)}
.side .me{margin-top:auto;display:flex;align-items:center;gap:10px;padding:12px 10px 4px;border-top:1px solid var(--color-border)}
.avatar{width:32px;height:32px;padding:1px;border-radius:999px;background:var(--soft);color:var(--color-primary);display:grid;place-items:center;font-weight:700;font-size:.8rem;flex:none}
.main{padding:26px clamp(16px,3vw,40px) 48px;min-width:0}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px 20px;flex-wrap:wrap;margin-bottom:22px}
.top .sub{color:var(--color-muted);margin-top:2px}.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.topbar{display:flex;align-items:center;gap:20px;padding:0 clamp(16px,3vw,40px);height:60px;background:var(--color-surface);border-bottom:1px solid var(--color-border);position:sticky;top:0;z-index:5}
.topbar nav{display:flex;gap:4px;margin-left:12px;overflow-x:auto;min-width:0}.topbar nav a{padding:8px 12px;border-radius:var(--r);color:var(--color-muted);text-decoration:none;font-weight:500;white-space:nowrap}
.topbar nav a[aria-current=page]{color:var(--color-ink);background:var(--soft);font-weight:600}.topbar .grow{flex:1}
/* controls */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:38px;padding:0 16px;border-radius:var(--r);border:1px solid var(--color-border);background:var(--color-surface);color:var(--color-ink);font:600 .9rem var(--font-body-md);cursor:pointer;text-decoration:none}
.btn:hover{background:var(--hover)}.btn--primary{background:var(--color-primary);border-color:var(--color-primary);color:var(--color-on-primary)}.btn--primary:hover{background:var(--color-primary);filter:brightness(1.08)}
.btn--ghost{border-color:transparent;background:transparent;color:var(--color-muted)}.btn--sm{min-height:32px;padding:0 12px;font-size:.85rem}.btn--danger{color:var(--color-danger);border-color:color-mix(in srgb,var(--color-danger) 40%,var(--color-border))}
.btn:disabled{opacity:.5;cursor:not-allowed}.btn--icon{width:38px;padding:0}.btn--sm.btn--icon{width:32px}
.field{display:grid;gap:6px;align-content:start}.field label,.label{font-weight:600;font-size:.88rem}.field .hint{font-size:.85rem;color:var(--color-muted)}
.input,.select,.textarea{width:100%;min-height:40px;padding:8px 12px;border-radius:var(--r);border:1px solid var(--field);background:var(--color-surface);color:var(--color-ink);font:400 .95rem var(--font-body-md)}
.textarea{min-height:96px;resize:vertical}.input::placeholder{color:var(--color-muted)}.input:hover,.select:hover{border-color:var(--color-ink)}
.input:focus-visible,.select:focus-visible,.textarea:focus-visible{outline:2px solid var(--color-primary);outline-offset:0;border-color:var(--color-primary)}
.field.is-error .input{border-color:var(--color-danger)}.field .error{color:var(--color-danger);font-size:.85rem;display:flex;gap:6px;align-items:center}
.search{position:relative;display:flex;align-items:center}.search .ico{position:absolute;left:11px;color:var(--color-muted)}.search .input{padding-left:36px}
.switch{position:relative;width:42px;height:24px;flex:none}.switch input{position:absolute;inset:0;opacity:0;margin:0;cursor:pointer}
.switch span{position:absolute;inset:0;border-radius:999px;background:color-mix(in srgb,var(--color-ink) 24%,var(--color-surface));transition:background .15s}
.switch span::after{content:"";position:absolute;left:3px;top:3px;width:18px;height:18px;border-radius:999px;background:var(--color-surface);box-shadow:var(--shadow);transition:transform .15s}
.switch input:checked+span{background:var(--color-primary)}.switch input:checked+span::after{transform:translateX(18px)}.switch input:focus-visible+span{outline:2px solid var(--color-primary);outline-offset:2px}
.check{display:inline-flex;align-items:center;gap:10px}.check input{width:18px;height:18px;accent-color:var(--color-primary);margin:0}
.seg{display:inline-flex;padding:3px;border-radius:var(--r);background:var(--hover);border:1px solid var(--color-border)}.seg button{border:0;background:transparent;color:var(--color-muted);font:600 .85rem var(--font-body-md);padding:6px 12px;border-radius:var(--r);cursor:pointer}
.seg button[aria-pressed=true]{background:var(--color-surface);color:var(--color-ink);box-shadow:var(--shadow)}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--color-border);overflow-x:auto}.tabs a{padding:10px 14px;color:var(--color-muted);text-decoration:none;font-weight:600;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap}
.tabs a[aria-current=page]{color:var(--color-ink);border-bottom-color:var(--color-primary)}
/* surfaces */
.card{background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}
.card>header,.card-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}.card-head p{color:var(--color-muted);font-size:.88rem}
.grid{display:grid;gap:16px}.cols-4{grid-template-columns:repeat(4,minmax(0,1fr))}.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}.cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi .label{color:var(--color-muted);font-weight:500;font-size:.88rem}.kpi .value{font:600 1.9rem/1.15 var(--font-display);letter-spacing:-.02em;margin:6px 0 4px;font-variant-numeric:tabular-nums}
.delta{display:inline-flex;align-items:center;gap:4px;font-size:.85rem;font-weight:600}.delta .ico{width:14px;height:14px}.delta--up{color:var(--color-ok)}.delta--down{color:var(--color-danger)}
.pill{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;font-size:.8rem;font-weight:600;line-height:1.5;white-space:nowrap;background:var(--hover);color:var(--color-muted)}
.pill::before{content:"";width:6px;height:6px;border-radius:999px;background:currentColor}
.pill--ok{background:color-mix(in srgb,var(--color-ok) 14%,var(--color-surface));color:var(--color-ok)}.pill--warn{background:color-mix(in srgb,var(--color-warn) 15%,var(--color-surface));color:var(--color-warn)}
.pill--danger{background:color-mix(in srgb,var(--color-danger) 13%,var(--color-surface));color:var(--color-danger)}.pill--info{background:var(--soft);color:var(--color-primary)}
.divider{height:1px;background:var(--color-border);border:0;margin:16px 0}
.list{list-style:none;margin:0;padding:0}.list li{display:flex;gap:12px;align-items:center;padding:11px 0;border-bottom:1px solid var(--color-border)}.list li:last-child{border-bottom:0}
/* tables */
.table-wrap{position:relative;overflow-x:auto;border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-surface)}
table{border-collapse:collapse;width:100%;font-size:.92rem}th{text-align:left;font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:var(--color-muted);font-weight:600;padding:11px 16px;border-bottom:1px solid var(--color-border);white-space:nowrap}thead{background:color-mix(in srgb,var(--color-ink) 3%,var(--color-surface))}
td{padding:12px 16px;border-bottom:1px solid var(--color-border);vertical-align:middle}tr:last-child td{border-bottom:0}tbody tr:hover td{background:var(--hover)}
td.r,th.r{text-align:right}th button{all:unset;cursor:pointer;display:inline-flex;gap:4px;align-items:center}th button:focus-visible{outline:2px solid var(--color-primary)}
.cell-main{display:flex;align-items:center;gap:12px;min-width:0}.cell-main b{display:block;font-weight:600}.cell-main span{color:var(--color-muted);font-size:.85rem}
.pager{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 4px 0;color:var(--color-muted);font-size:.9rem}
/* charts: SVG for the shape, HTML for the labels, so text stays readable at every width */
.chart{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 10px}.chart .ys{display:flex;flex-direction:column;justify-content:space-between;font-size:.75rem;color:var(--color-muted);text-align:right;padding:2px 0}
.chart svg{width:100%;height:100%;display:block}.chart .plot{height:var(--h,220px);position:relative}.chart .xs{grid-column:2;display:flex;justify-content:space-between;font-size:.75rem;color:var(--color-muted);padding-top:8px}
.bars{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:10px;align-items:end;height:var(--h,180px)}.bars div{background:var(--color-primary);border-radius:6px;min-height:4px;position:relative}
.bars div.alt{background:color-mix(in srgb,var(--color-primary) 35%,var(--color-surface))}.bar-labels{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:10px;font-size:.75rem;color:var(--color-muted);text-align:center;padding-top:8px}
.meter{height:8px;border-radius:999px;background:var(--hover);overflow:hidden;border:1px solid var(--color-border)}.meter i{display:block;height:100%;background:var(--color-primary);border-radius:999px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.85rem;color:var(--color-muted)}.legend i{display:inline-block;width:10px;height:10px;border-radius:6px;margin-right:6px;vertical-align:-1px}
/* narrow screens: the sidebar becomes a strip, grids stack, tables scroll inside their frame */
@media (max-width:1100px){.cols-4{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:860px){.app{grid-template-columns:minmax(0,1fr)}.side{position:static;height:auto;flex-direction:row;align-items:center;gap:6px;padding:10px 12px;border-right:0;border-bottom:1px solid var(--color-border);overflow-x:auto}
.side .brand{padding:0 8px 0 0}.side .nav-title,.side .me{display:none}.nav{display:flex;gap:2px}.nav a{white-space:nowrap}.cols-3,.cols-2,.cols-4{grid-template-columns:minmax(0,1fr)}.main{padding:18px 16px 40px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def root_block(palette: str, font: str, extra: str = "") -> str:
    colours = PALETTES[palette]
    display, body, mono = FONTS[font]
    variables = "".join(f"--color-{name}:{value};" for name, value in colours.items())
    scheme = "color-scheme:dark;" if palette == "ink" else ""
    return f":root{{{variables}{scheme}--font-display:{display};--font-body-md:{body};--font-mono:{mono};{extra}}}"


def page(
    title: str,
    note: str,
    palette: str,
    font: str,
    css: str,
    body: str,
    icons: list[str],
    extra_root: str = "",
) -> str:
    """One complete standalone file: head with the token block, the shared stylesheet, the screen's own CSS and its body."""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n<!-- SCREEN: {note}\n     Replace the :root block with the tokens exported from DESIGN.md (design_md_export css-variables) and delete it;"
        " change every word and number to the product's own; keep the structure that fits. -->\n<style>\n"
        f"{root_block(palette, font, extra_root)}\n{BASE_CSS.strip()}\n{css.strip()}\n</style>\n</head>\n<body>\n{sprite(icons)}\n{body.strip()}\n</body>\n</html>\n"
    )


# --- chart builders ---------------------------------------------------------------------------------------------------------------------------


def _points(
    values: list[float], width: float, height: float, low: float, high: float
) -> list[tuple[float, float]]:
    step = width / (len(values) - 1)
    return [
        (round(i * step, 1), round(height - (v - low) / (high - low) * height, 1))
        for i, v in enumerate(values)
    ]


def line_chart(
    series: list[tuple[list[float], str]],
    y_labels: list[str],
    x_labels: list[str],
    height: int = 220,
    area: bool = True,
    label: str = "Trend chart",
) -> str:
    """Smooth-ish line(s) over a grid: the shape is SVG, the axis text is HTML next to it."""
    low = min(min(values) for values, _ in series)
    high = max(max(values) for values, _ in series)
    pad = (high - low) * 0.12 or 1
    low, high = low - pad, high + pad
    width, h = 600.0, 200.0
    parts = [
        f'<svg viewBox="0 0 {width:.0f} {h:.0f}" preserveAspectRatio="none" role="img" aria-label="{label}">'
    ]
    for i in range(5):
        y = i * h / 4
        parts.append(
            f'<line x1="0" x2="{width:.0f}" y1="{y:.0f}" y2="{y:.0f}" stroke="var(--color-border)" stroke-width="1" vector-effect="non-scaling-stroke"/>'
        )
    for index, (values, colour) in enumerate(series):
        points = _points(values, width, h, low, high)
        path = "M" + " L".join(f"{x},{y}" for x, y in points)
        if area and index == 0:
            parts.append(f'<path d="{path} L{width:.0f},{h:.0f} L0,{h:.0f}Z" fill="{colour}" opacity=".12"/>')
        parts.append(
            f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
        )
        x, y = points[-1]
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="4.5" fill="{colour}" stroke="var(--color-surface)" stroke-width="2" vector-effect="non-scaling-stroke"/>'
        )
    parts.append("</svg>")
    ys = "".join(f"<span>{text}</span>" for text in y_labels)
    xs = "".join(f"<span>{text}</span>" for text in x_labels)
    return f'<div class="chart" style="--h:{height}px"><div class="ys">{ys}</div><div class="plot">{"".join(parts)}</div><div class="xs">{xs}</div></div>'


def bar_chart(
    values: list[float],
    labels: list[str],
    height: int = 180,
    highlight: int | None = None,
    title: str = "Bar chart",
) -> str:
    top = max(values)
    cells = "".join(
        f'<div class="{"" if highlight is None or i == highlight else "alt"}" style="height:{v / top * 100:.0f}%" title="{labels[i]}: {v:g}"></div>'
        for i, v in enumerate(values)
    )
    names = "".join(f"<span>{name}</span>" for name in labels)
    return f'<div role="img" aria-label="{title}"><div class="bars" style="--h:{height}px">{cells}</div><div class="bar-labels">{names}</div></div>'


def donut(
    parts: list[tuple[float, str]], size: int = 150, thickness: int = 18, centre: str = "", sub: str = ""
) -> str:
    """A ring of proportional arcs with the total in the middle (HTML text over SVG)."""
    total = sum(value for value, _ in parts)
    radius = (size - thickness) / 2
    circumference = 6.2832 * radius
    offset = 0.0
    arcs = []
    for value, colour in parts:
        length = value / total * circumference
        arcs.append(
            f'<circle cx="{size / 2}" cy="{size / 2}" r="{radius}" fill="none" stroke="{colour}" stroke-width="{thickness}" '
            f'stroke-dasharray="{length - 3:.1f} {circumference - length + 3:.1f}" stroke-dashoffset="{-offset:.1f}" transform="rotate(-90 {size / 2} {size / 2})"/>'
        )
        offset += length
    return (
        f'<div style="position:relative;width:{size}px;height:{size}px;flex:none"><svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="Share by category">'
        f'<circle cx="{size / 2}" cy="{size / 2}" r="{radius}" fill="none" stroke="var(--color-border)" stroke-width="{thickness}"/>{"".join(arcs)}</svg>'
        f'<div style="position:absolute;inset:0;display:grid;place-content:center;text-align:center"><b class="num" style="font:600 1.5rem var(--font-display)">{centre}</b><span class="muted" style="font-size:.8rem">{sub}</span></div></div>'
    )


def spark(
    values: list[float], colour: str = "var(--color-primary)", width: int = 96, height: int = 32
) -> str:
    low, high = min(values), max(values)
    points = _points(values, width, height - 4, low, high if high > low else low + 1)
    path = "M" + " L".join(f"{x},{y + 2:.1f}" for x, y in points)
    return f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true"><path d="{path}" fill="none" stroke="{colour}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def sidebar(
    brand: str,
    mark: str,
    items: list[tuple[str, str, str]],
    current: str,
    sections: list[tuple[str, list[tuple[str, str, str]]]] | None = None,
    person: tuple[str, str, str] = ("AM", "Ana Moreno", "Operations lead"),
) -> str:
    """The side navigation: items are (icon, label, count); `current` is the label that is the open page."""

    def links(entries: list[tuple[str, str, str]]) -> str:
        return "".join(
            f'<a href="#" {"aria-current=page" if label == current else ""}>{icon(ic)}{label}{f"<span class=count>{count}</span>" if count else ""}</a>'
            for ic, label, count in entries
        )

    extra = "".join(
        f'<div class="nav-title">{title}</div><div class="nav">{links(entries)}</div>'
        for title, entries in (sections or [])
    )
    initials, name, role = person
    return (
        f'<aside class="side" aria-label="Main"><div class="brand"><i>{mark}</i>{brand}</div><nav class="nav" aria-label="Primary">{links(items)}</nav>{extra}'
        f'<div class="me"><span class="avatar">{initials}</span><div><b style="font-size:.9rem">{name}</b><div class="muted" style="font-size:.8rem">{role}</div></div></div></aside>'
    )
