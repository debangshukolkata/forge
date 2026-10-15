"""Inputs and cards (D-382). Plain CSS, tokens with fallbacks, no JavaScript."""

from __future__ import annotations

from .model import Effect

P = "var(--color-primary,#4f46e5)"
INK = "var(--color-ink,#111827)"
MUTED = "var(--color-muted,#4b5563)"
SURFACE = "var(--color-surface,#fff)"
BORDER = "var(--color-border,#d1d5db)"
DANGER = "var(--color-danger,#b42318)"
FIELD = f"font:400 .95rem var(--font-body-md,system-ui);padding:.65rem .85rem;border:1px solid {BORDER};border-radius:var(--r,10px);background:{SURFACE};color:{INK};width:100%"

INPUTS = [
    Effect(
        "mi-input-float-label",
        "input",
        "Floating label",
        "A label that sits in the field and floats above it when the field is focused or filled.",
        f".mi-input-float-label{{position:relative;display:block;padding-top:1rem}}.mi-input-float-label input{{{FIELD}}}.mi-input-float-label label{{position:absolute;left:.85rem;top:1.7rem;color:{MUTED};pointer-events:none;transform-origin:left top;transition:transform .18s,color .18s}}"
        f".mi-input-float-label input:focus~label,.mi-input-float-label input:not(:placeholder-shown)~label{{transform:translateY(-1.55rem) scale(.8);color:{P}}}.mi-input-float-label input:focus-visible{{outline:2px solid {P};outline-offset:1px}}",
        '<div class="mi-input-float-label"><input id="mi-f1" placeholder=" "><label for="mi-f1">Email address</label></div>',
        "focus:input",
        "label",
        "transform",
        'Keep placeholder=" " on the input: the CSS reads :placeholder-shown.',
    ),
    Effect(
        "mi-input-underline-grow",
        "input",
        "Growing underline",
        "A minimal field whose underline grows from the centre when focused.",
        f".mi-input-underline-grow{{display:block;background:linear-gradient({P},{P}) no-repeat center bottom/0 2px;border-bottom:1px solid {BORDER};transition:background-size .3s}}.mi-input-underline-grow input{{width:100%;border:0;background:transparent;padding:.6rem .1rem;font:400 1rem var(--font-body-md,system-ui);color:{INK};outline:none}}"
        f".mi-input-underline-grow:focus-within{{background-size:100% 2px}}",
        '<div class="mi-input-underline-grow"><input aria-label="Name" placeholder="Your name"></div>',
        "focus:input",
        "",
        "background-size",
        "The wrapper draws the line, so the input's own outline is removed: keep the growing line visible enough (2 px).",
        moods=("editorial", "calm"),
    ),
    Effect(
        "mi-input-ring",
        "input",
        "Focus ring",
        "A soft ring that grows around a field when it is focused.",
        f".mi-input-ring{{{FIELD};box-shadow:0 0 0 0 color-mix(in srgb,{P} 0%,transparent);transition:box-shadow .2s,border-color .2s}}.mi-input-ring:focus{{outline:none;border-color:{P};box-shadow:0 0 0 4px color-mix(in srgb,{P} 25%,transparent)}}",
        '<input class="mi-input-ring" aria-label="Postcode" placeholder="Postcode">',
        "focus",
        "",
        "box-shadow",
        "The ring is the focus indicator: do not remove it.",
    ),
    Effect(
        "mi-input-glow",
        "input",
        "Glow focus",
        "A coloured glow and a stronger border on focus: for dark interfaces.",
        f".mi-input-glow{{{FIELD};transition:box-shadow .25s,border-color .25s}}.mi-input-glow:focus{{outline:none;border-color:{P};box-shadow:0 0 0 1px {P},0 0 18px color-mix(in srgb,{P} 55%,transparent)}}",
        '<input class="mi-input-glow" aria-label="Command" placeholder="Type a command">',
        "focus",
        "",
        "border-top-color",
        "Best on dark surfaces; on light ones prefer mi-input-ring.",
        moods=("technical", "dark"),
    ),
    Effect(
        "mi-input-invalid-shake",
        "input",
        "Invalid shake",
        "A field that shakes once and shows a red border when its value is invalid after the person leaves it.",
        f".mi-input-invalid-shake{{{FIELD};transition:border-color .2s}}.mi-input-invalid-shake:user-invalid{{border-color:{DANGER};animation:mi-field-shake .35s}}@keyframes mi-field-shake{{20%{{transform:translateX(-6px)}}40%{{transform:translateX(5px)}}60%{{transform:translateX(-3px)}}80%{{transform:translateX(2px)}}}}",
        '<input class="mi-input-invalid-shake" type="email" required aria-label="Email" placeholder="you@example.com">',
        "invalid",
        "",
        "animation-name",
        "Uses :user-invalid, so nothing happens before the person has typed; always show the error text as well, never motion alone.",
        moods=("clear", "robust"),
    ),
    Effect(
        "mi-input-search-expand",
        "input",
        "Expanding search",
        "A search field that is an icon button until focused, then opens wide.",
        f".mi-input-search-expand{{display:flex;align-items:center;width:44px;height:44px;border:1px solid {BORDER};border-radius:99px;background:{SURFACE};overflow:hidden;transition:width .3s,border-color .3s}}.mi-input-search-expand svg{{flex:none;width:44px;padding:12px;fill:none;stroke:{MUTED};stroke-width:2;stroke-linecap:round}}"
        f".mi-input-search-expand input{{flex:1;min-width:0;border:0;background:transparent;padding:0 .8rem 0 0;font:400 .95rem var(--font-body-md,system-ui);color:{INK};outline:none}}.mi-input-search-expand:focus-within{{width:260px;border-color:{P}}}",
        '<div class="mi-input-search-expand"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg><input type="search" aria-label="Search"></div>',
        "focus:input",
        "",
        "width",
        "Collapsed it is a 44 px target; on a phone let it open to the full width of the header.",
    ),
    Effect(
        "mi-input-prefix-focus",
        "input",
        "Prefix that lights up",
        "A field with a currency or unit prefix that takes the accent colour when the field is focused.",
        f".mi-input-prefix-focus{{display:flex;align-items:stretch;border:1px solid {BORDER};border-radius:var(--r,10px);background:{SURFACE};overflow:hidden;transition:border-color .2s}}.mi-input-prefix-focus i{{display:grid;place-items:center;padding:0 .85rem;font-style:normal;font-weight:600;color:{MUTED};background:color-mix(in srgb,{INK} 5%,{SURFACE});transition:color .2s,background .2s}}"
        f".mi-input-prefix-focus input{{flex:1;min-width:0;border:0;padding:.65rem .85rem;font:400 .95rem var(--font-body-md,system-ui);background:transparent;color:{INK};outline:none}}.mi-input-prefix-focus:focus-within{{border-color:{P}}}.mi-input-prefix-focus:focus-within i{{color:var(--color-on-primary,#fff);background:{P}}}",
        '<div class="mi-input-prefix-focus"><i>&euro;</i><input inputmode="decimal" aria-label="Amount" placeholder="0.00"></div>',
        "focus:input",
        "i",
        "background-color",
        "The prefix is decoration: put the unit in the label too for screen readers.",
    ),
    Effect(
        "mi-select-arrow",
        "input",
        "Turning select arrow",
        "A select whose chevron turns over when the field is focused or open.",
        f".mi-select-arrow{{position:relative;display:block}}.mi-select-arrow select{{{FIELD};appearance:none;padding-right:2.4rem;cursor:pointer}}.mi-select-arrow i{{position:absolute;right:1rem;top:50%;width:.55rem;height:.55rem;border-right:2px solid {MUTED};border-bottom:2px solid {MUTED};transform:translateY(-70%) rotate(45deg);transition:transform .2s;pointer-events:none}}"
        f".mi-select-arrow:focus-within i{{transform:translateY(-30%) rotate(225deg)}}.mi-select-arrow select:focus-visible{{outline:2px solid {P};outline-offset:1px}}",
        '<div class="mi-select-arrow"><select aria-label="Country"><option>Germany</option><option>France</option></select><i></i></div>',
        "focus:select",
        "i",
        "transform",
        "A native select underneath: it keeps its keyboard and phone behaviour.",
    ),
]

CARDS = [
    Effect(
        "mi-card-lift",
        "card",
        "Lift",
        "A card that rises and gains a deeper shadow on hover.",
        f".mi-card-lift{{padding:1.2rem;border:1px solid {BORDER};border-radius:var(--radius,14px);background:{SURFACE};box-shadow:0 1px 2px #0001;transition:transform .2s,box-shadow .2s}}.mi-card-lift:hover,.mi-card-lift:focus-within{{transform:translateY(-6px);box-shadow:0 18px 30px -14px #0003}}",
        '<article class="mi-card-lift"><h3>Riverside Depot</h3><p>Open until 20:00</p><a href="#">Details</a></article>',
        "hover",
        "",
        "transform",
        "For cards that are links: make the whole card clickable with a stretched link, not only the title.",
    ),
    Effect(
        "mi-card-tilt",
        "card",
        "Gentle tilt",
        "A card that tilts a few degrees in 3D as if lifted at one corner.",
        f".mi-card-tilt{{padding:1.2rem;border:1px solid {BORDER};border-radius:var(--radius,14px);background:{SURFACE};transform:perspective(700px) rotateX(0) rotateY(0);transition:transform .25s,box-shadow .25s}}.mi-card-tilt:hover{{transform:perspective(700px) rotateX(4deg) rotateY(-5deg) translateY(-4px);box-shadow:0 20px 30px -16px #0003}}",
        '<article class="mi-card-tilt"><h3>Poster night</h3><p>Friday, 19:30</p></article>',
        "hover",
        "",
        "transform",
        "Small angles only (under 6 degrees); it is a pointer effect, nothing happens on touch.",
        moods=("playful", "modern"),
    ),
    Effect(
        "mi-card-border-gradient",
        "card",
        "Moving gradient border",
        "A two-colour gradient border that slides around the card on hover.",
        f".mi-card-border-gradient{{padding:1.2rem;border:2px solid transparent;border-radius:var(--radius,14px);background:linear-gradient({SURFACE},{SURFACE}) padding-box,linear-gradient(120deg,{P},var(--color-accent2,#f59e0b),{P}) border-box;background-size:100% 100%,300% 300%;background-position:0 0,0% 50%;transition:background-position 1.2s}}"
        ".mi-card-border-gradient:hover{background-position:0 0,100% 50%}",
        '<article class="mi-card-border-gradient"><h3>Featured plan</h3><p>Most people choose this.</p></article>',
        "hover",
        "",
        "background-position",
        "Mark one card as featured; the effect loses meaning if every card has it.",
    ),
    Effect(
        "mi-card-reveal-overlay",
        "card",
        "Slide-up details",
        "A picture card whose details slide up from the bottom on hover or focus.",
        f".mi-card-reveal-overlay{{position:relative;overflow:hidden;border-radius:var(--radius,14px);min-height:180px;background:linear-gradient(135deg,{P},var(--color-accent2,#f59e0b))}}.mi-card-reveal-overlay .o{{position:absolute;left:0;right:0;bottom:0;padding:1rem;background:color-mix(in srgb,{INK} 88%,transparent);color:#fff;transform:translateY(100%);transition:transform .3s}}"
        ".mi-card-reveal-overlay:hover .o,.mi-card-reveal-overlay:focus-within .o{transform:translateY(0)}",
        '<article class="mi-card-reveal-overlay" tabindex="0"><div class="o"><b>Harbour Pickup</b><p>Opens 08:00 on weekdays</p></div></article>',
        "hover",
        ".o",
        "transform",
        "The details must also be reachable without hover (they are, on focus); on a phone show them always.",
    ),
    Effect(
        "mi-card-flip",
        "card",
        "Flip card",
        "A card that turns over to show its back on hover or focus.",
        f".mi-card-flip{{perspective:800px;min-height:150px}}.mi-card-flip .in{{position:relative;min-height:150px;transform-style:preserve-3d;transition:transform .5s}}.mi-card-flip .f,.mi-card-flip .b{{position:absolute;inset:0;padding:1.1rem;border:1px solid {BORDER};border-radius:var(--radius,14px);backface-visibility:hidden}}"
        f".mi-card-flip .f{{background:{SURFACE}}}.mi-card-flip .b{{background:{P};color:var(--color-on-primary,#fff);transform:rotateY(180deg)}}.mi-card-flip:hover .in,.mi-card-flip:focus-within .in{{transform:rotateY(180deg)}}",
        '<article class="mi-card-flip" tabindex="0"><div class="in"><div class="f"><h3>Who can give?</h3></div><div class="b"><p>Anyone aged 17 to 65 in good health.</p></div></div></article>',
        "hover",
        ".in",
        "transform",
        "Only for short, optional content on the back; do not hide what people need.",
        moods=("playful", "friendly"),
    ),
    Effect(
        "mi-card-image-zoom",
        "card",
        "Image zoom",
        "A card whose picture zooms slowly inside its frame on hover.",
        f".mi-card-image-zoom{{overflow:hidden;border-radius:var(--radius,14px);border:1px solid {BORDER};background:{SURFACE}}}.mi-card-image-zoom svg{{display:block;width:100%;height:140px;transition:transform .6s ease}}.mi-card-image-zoom:hover svg,.mi-card-image-zoom:focus-within svg{{transform:scale(1.08)}}.mi-card-image-zoom p{{margin:0;padding:.9rem 1rem;position:relative;background:{SURFACE}}}",
        '<article class="mi-card-image-zoom"><svg viewBox="0 0 200 140" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="200" height="140" fill="#6366f1"/><circle cx="150" cy="40" r="26" fill="#fde68a"/><path d="M0 110c40-30 80-20 120 0s60 10 80-10v50H0z" fill="#4338ca"/></svg><p>Autumn programme</p></article>',
        "hover",
        "svg",
        "transform",
        "Give the picture overflow:hidden on its frame, as here, or the zoom spills over the card edge.",
    ),
    Effect(
        "mi-card-corner-fold",
        "card",
        "Folding corner",
        "A card with a corner that folds open a little on hover.",
        f".mi-card-corner-fold{{position:relative;padding:1.2rem;border:1px solid {BORDER};border-radius:var(--radius,14px);background:{SURFACE};overflow:hidden}}.mi-card-corner-fold i{{position:absolute;top:0;right:0;width:0;height:0;background:linear-gradient(225deg,{SURFACE} 50%,color-mix(in srgb,{P} 35%,{SURFACE}) 50%);box-shadow:-3px 3px 6px #0002;transition:width .25s,height .25s}}"
        ".mi-card-corner-fold:hover i,.mi-card-corner-fold:focus-within i{width:34px;height:34px}",
        '<article class="mi-card-corner-fold"><i></i><h3>Invoice 2025-03</h3><p>Paid on 3 March</p></article>',
        "hover",
        "i",
        "width",
        "A document metaphor: invoices, notes, letters.",
        moods=("editorial", "calm"),
    ),
    Effect(
        "mi-card-stack-fan",
        "card",
        "Fanning stack",
        "A stack of sheets behind a card that fan out when the card is hovered.",
        f".mi-card-stack-fan{{position:relative;padding:1.2rem;border:1px solid {BORDER};border-radius:var(--radius,14px);background:{SURFACE};z-index:1}}.mi-card-stack-fan i{{position:absolute;inset:0;border:1px solid {BORDER};border-radius:var(--radius,14px);background:color-mix(in srgb,{INK} 4%,{SURFACE});z-index:-1;transform-origin:50% 100%;transition:transform .3s}}"
        ".mi-card-stack-fan:hover i:nth-of-type(1),.mi-card-stack-fan:focus-within i:nth-of-type(1){transform:rotate(-4deg) translateY(-6px)}.mi-card-stack-fan:hover i:nth-of-type(2),.mi-card-stack-fan:focus-within i:nth-of-type(2){transform:rotate(4deg) translateY(-3px)}",
        '<article class="mi-card-stack-fan"><i></i><i></i><h3>Photo set</h3><p>24 pictures</p></article>',
        "hover",
        "i",
        "transform",
        "The stack hints at more behind it: albums, collections, versions.",
    ),
]

SURFACES = [*INPUTS, *CARDS]
