"""A specimen page for a design system (D-350): the tokens applied to a standard set of components, so a design can be looked at (and judged by the
critic) before any real page exists. Pure HTML and CSS built from the tokens, no scripts, no network."""

from __future__ import annotations

from html import escape
from typing import Any

from forge.designsystem.export import export
from forge.designsystem.spec import DesignSystem

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>
{tokens}
*{{box-sizing:border-box}}
body{{margin:0;background:{neutral};color:{ink};font-family:{body_font};font-size:{body_size};line-height:1.6}}
h1,h2,h3{{font-family:{display_font};margin:0;line-height:1.1;letter-spacing:{tracking}}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 32px}}
nav{{display:flex;justify-content:space-between;align-items:center;padding:20px 0;border-bottom:1px solid {border}}}
nav b{{font-family:{display_font};font-size:20px}} nav span{{margin-left:24px;color:{muted}}}
.hero{{padding:72px 0 56px;display:grid;grid-template-columns:1.2fr 1fr;gap:48px;align-items:center}}
.hero h1{{font-size:{display_size};font-weight:{display_weight}}} .hero p{{color:{muted};font-size:18px;max-width:34em;margin:20px 0 28px}}
.btn{{display:inline-block;padding:12px 24px;border-radius:{radius_button};font-weight:600;text-decoration:none;margin-right:12px;border:1.5px solid {primary}}}
.btn.p{{background:{primary};color:{on_primary}}} .btn.s{{background:transparent;color:{primary}}}
.panel{{background:{surface};border:1px solid {border};border-radius:{radius_card};padding:28px;min-height:230px}}
.row{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin:24px 0 40px}}
.card{{background:{surface};border:1px solid {border};border-radius:{radius_card};padding:24px}}
.card h3{{font-size:20px;margin-bottom:8px}} .card p{{margin:0;color:{muted}}}
.eyebrow{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:{primary};font-weight:700;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse;margin:8px 0 32px}} th{{text-align:left;color:{muted};font-size:13px;padding:10px 12px;border-bottom:1px solid {border}}}
td{{padding:12px;border-bottom:1px solid {border};font-variant-numeric:tabular-nums}} td.n,th.n{{text-align:right}}
.form{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:40px}} label{{font-size:13px;color:{muted};display:block;margin-bottom:6px}}
.in{{border:1px solid {border};background:{neutral};border-radius:{radius_input};padding:12px;color:{muted}}}
.chips span{{display:inline-block;margin-right:8px;padding:4px 12px;border-radius:999px;font-size:13px;font-weight:600}}
.sw{{display:flex;gap:10px;margin:16px 0 56px}} .sw div{{flex:1;height:56px;border-radius:{radius_card};border:1px solid {border};font-size:11px;padding:6px;color:#fff}}
footer{{border-top:1px solid {border};padding:24px 0;color:{muted};font-size:13px}}
</style></head><body><div class="wrap">
<nav><b>{name}</b><div><span>Product</span><span>Pricing</span><span>About</span><span style="color:{primary};font-weight:600">Sign in</span></div></nav>
<section class="hero"><div><div class="eyebrow">{eyebrow}</div><h1>{headline}</h1><p>{lede}</p>
<a class="btn p" href="#">Get started</a><a class="btn s" href="#">See how it works</a></div><div class="panel"><div class="eyebrow">This month</div>
<h2 style="font-size:44px">4,218</h2><p style="color:{muted};margin:6px 0 0">orders shipped, up 12% on last month</p></div></section>
<div class="row"><div class="card"><h3>Clear hierarchy</h3><p>One idea per block, a calm rhythm and room to breathe.</p></div>
<div class="card"><h3>Honest detail</h3><p>Numbers, labels and states are written for the person using them.</p></div>
<div class="card"><h3>Built to last</h3><p>Every value comes from the design system, not from habit.</p></div></div>
<table><tr><th>Order</th><th>Customer</th><th>Status</th><th class="n">Amount</th></tr>
<tr><td>#10482</td><td>Asha Verma</td><td>Shipped</td><td class="n">1,240.00</td></tr><tr><td>#10483</td><td>Daniel Okafor</td><td>Packing</td><td class="n">86.50</td></tr>
<tr><td>#10484</td><td>Mei Tanaka</td><td>Refunded</td><td class="n">312.75</td></tr></table>
<div class="form"><div><label>Full name</label><div class="in">Asha Verma</div></div><div><label>Email</label><div class="in">asha@example.com</div></div></div>
<div class="chips"><span style="background:{ok_fill};color:{ok}">Paid</span><span style="background:{warn_fill};color:{warn}">Pending</span><span style="background:{error_fill};color:{error}">Failed</span></div>
<div class="sw">{swatches}</div><footer>{name} &middot; specimen of the design system &middot; {fonts}</footer></div></body></html>"""


def _tint(colour: str, base: str = "#FFFFFF", share: float = 0.88) -> str:
    """`colour` washed toward `base` (white on a light page, the page colour on a dark one) for a quiet status background."""
    from forge.designsystem.colour import parse

    parsed, floor = parse(colour), parse(base)
    if parsed is None or floor is None:
        return "#EEEEEE"
    return "#{:02X}{:02X}{:02X}".format(
        *(round(c + (b - c) * share) for c, b in zip(parsed[:3], floor[:3], strict=True))
    )


def specimen_html(system: DesignSystem, headline: str = "", lede: str = "", eyebrow: str = "") -> str:
    """The specimen page for `system`. Missing tokens fall back to neutral defaults, so a half-written system can still be looked at."""
    from forge.brand.kit import readable_on
    from forge.designsystem.colour import parse, to_hex

    def colour(*names: str, default: str) -> str:
        for name in names:
            if name in system.colors:
                return str(system.resolve(system.colors[name]))
        return default

    primary = colour("primary", "accent", default="#1F3864")
    neutral = colour("neutral", "canvas", "background", "bg", default="#FFFFFF")
    ink = colour("ink", "text", "foreground", default="#111827")
    muted = colour("muted", default="#4B5563")
    surface = colour("surface", default=neutral)
    border = colour("border", "hairline", default="#D1D5DB")
    ok, warn, error = (
        colour("ok", default="#15803D"),
        colour("warn", default="#B45309"),
        colour("error", default="#B91C1C"),
    )
    parsed = parse(primary)
    on_primary = "#" + readable_on(to_hex(parsed)) if parsed else "#FFFFFF"
    display: Any = system.typography.get("display") or system.typography.get("h1") or {}
    body: Any = system.typography.get("body-md") or next(iter(system.typography.values()), {})

    def font(style: object, fallback: str) -> str:
        family = (
            str(system.resolve(style.get("fontFamily")))
            if isinstance(style, dict) and style.get("fontFamily")
            else fallback
        )
        parts = [p.strip().strip("\"'") for p in family.split(",") if p.strip()]
        return ", ".join(f'"{p}"' if " " in p else p for p in parts) + ", system-ui, sans-serif"

    def rounded(*names: str, default: str) -> str:
        for name in names:
            if name in system.rounded:
                return str(system.resolve(system.rounded[name]))
        return default

    tokens = export(system, "css-variables") if (system.colors or system.typography) else ""
    swatches = "".join(
        f'<div style="background:{system.resolve(value)};color:#{readable_on(to_hex(p) if (p := parse(str(system.resolve(value)))) else "FFFFFF")}">{escape(name)}</div>'
        for name, value in list(system.colors.items())[:8]
    )
    return PAGE.format(
        title=escape(system.name),
        name=escape(system.name),
        tokens=tokens,
        neutral=neutral,
        ink=ink,
        muted=muted,
        surface=surface,
        border=border,
        primary=primary,
        on_primary=on_primary,
        body_font=font(body, "Inter"),
        display_font=font(display, "Georgia"),
        body_size=str(system.resolve(body.get("fontSize", "16px"))) if isinstance(body, dict) else "16px",
        display_size=str(system.resolve(display.get("fontSize", "56px")))
        if isinstance(display, dict)
        else "56px",
        display_weight=str(system.resolve(display.get("fontWeight", 700)))
        if isinstance(display, dict)
        else "700",
        tracking=str(system.resolve(display.get("letterSpacing", "-0.01em")))
        if isinstance(display, dict)
        else "-0.01em",
        radius_button=rounded("pill", "md", default="999px")
        if "pill" in system.rounded
        else rounded("md", "sm", default="8px"),
        radius_card=rounded("md", "lg", "sm", default="12px"),
        radius_input=rounded("sm", "md", default="8px"),
        ok=ok,
        warn=warn,
        error=error,
        ok_fill=_tint(ok, neutral, 0.82),
        warn_fill=_tint(warn, neutral, 0.82),
        error_fill=_tint(error, neutral, 0.82),
        headline=escape(headline or "A calmer way to run your shop"),
        lede=escape(lede or "Orders, customers and payments in one place, with nothing you do not need."),
        eyebrow=escape(eyebrow or system.name),
        swatches=swatches,
        fonts=escape(
            ", ".join(
                dict.fromkeys(
                    str(system.resolve(s.get("fontFamily", ""))).split(",")[0].strip().strip("\"'")
                    for s in system.typography.values()
                    if isinstance(s, dict) and s.get("fontFamily")
                )
            )
        ),
    )
