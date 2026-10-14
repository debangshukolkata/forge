"""Five screens for putting data in: a multi-step wizard, invoice-style line entry, a long single-page form with errors, a sign-in split screen and quick capture (D-366)."""

from __future__ import annotations

from .kit import icon, sidebar
from .screen import Screen

SPLIT = "@media (max-width:1000px){#split{grid-template-columns:minmax(0,1fr)!important}}"


def _field(label: str, control: str, hint: str = "", error: str = "", for_id: str = "") -> str:
    err = f'<p class="error" id="{for_id}-e">{icon("x")}{error}</p>' if error else ""
    note = f'<p class="hint">{hint}</p>' if hint and not error else ""
    return f'<div class="field{" is-error" if error else ""}"><label for="{for_id}">{label}</label>{control}{note}{err}</div>'


def wizard() -> Screen:
    steps = [("Company", "done"), ("Team", "done"), ("Billing", "now"), ("Review", "")]
    stepper = "".join(
        f'<li class="step step--{state or "todo"}"{" aria-current=step" if state == "now" else ""}><span class="dot">{icon("check") if state == "done" else i + 1}</span><span>{name}</span></li>'
        for i, (name, state) in enumerate(steps)
    )
    css = (
        ".steps{display:flex;gap:8px;list-style:none;margin:0 0 28px;padding:0;flex-wrap:wrap}.step{display:flex;align-items:center;gap:10px;flex:1;min-width:130px;font-weight:600;color:var(--color-muted)}"
        ".step .dot{width:30px;height:30px;padding:1px;border-radius:999px;border:2px solid var(--color-border);display:grid;place-items:center;font-size:.85rem;flex:none;background:var(--color-surface)}"
        ".step .dot .ico{width:15px;height:15px}.step--done .dot{background:var(--color-primary);border-color:var(--color-primary);color:var(--color-on-primary)}.step--now{color:var(--color-ink)}.step--now .dot{border-color:var(--color-primary);color:var(--color-primary)}"
        '.step:not(:last-child)::after{content:"";flex:1;height:2px;background:var(--color-border);margin-left:4px;min-width:16px}.step--done:not(:last-child)::after{background:var(--color-primary)}'
        ".plan{display:block;border:1.5px solid var(--color-border);border-radius:var(--radius);padding:16px;cursor:pointer;background:var(--color-surface)}.plan:has(input:checked){border-color:var(--color-primary);background:var(--soft)}"
        ".plan input{accent-color:var(--color-primary);margin-right:10px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.form-grid .wide{grid-column:1/-1}"
        "@media (max-width:700px){.form-grid{grid-template-columns:minmax(0,1fr)}}"
    )
    body = f"""
<main class="main" style="max-width:1020px;margin:0 auto;padding-top:34px">
  <div class="brand" style="padding:0 0 22px"><i>K</i>Kiln</div>
  <div class="top" style="margin-bottom:8px"><div><h1>Set up your workspace</h1><p class="sub">Step 3 of 4 · you can change all of this later</p></div><a class="btn btn--ghost" href="#">Save and exit</a></div>
  <ol class="steps" aria-label="Progress">{stepper}</ol>
  <div class="grid" style="grid-template-columns:minmax(0,3fr) minmax(0,2fr);align-items:start" id="split">
    <form class="card" aria-labelledby="bill" style="padding:26px">
      <h2 id="bill" style="font-size:1.25rem;margin-bottom:4px">Billing details</h2><p class="muted" style="margin-bottom:22px">We send invoices here. Nothing is charged until your trial ends.</p>
      <fieldset style="border:0;padding:0;margin:0 0 22px"><legend class="label" style="margin-bottom:10px">Plan</legend>
        <div class="grid cols-2" style="gap:12px"><label class="plan"><input type="radio" name="plan"><b>Team</b> <span class="muted">· $12 per seat</span><p class="muted" style="margin:4px 0 0 24px;font-size:.9rem">Up to 25 people, shared projects</p></label>
        <label class="plan"><input type="radio" name="plan" checked><b>Business</b> <span class="muted">· $24 per seat</span><p class="muted" style="margin:4px 0 0 24px;font-size:.9rem">Single sign-on, audit log, priority help</p></label></div></fieldset>
      <div class="form-grid">
        {_field("Company legal name", '<input class="input" id="legal" value="Kiln Ceramics Ltd" autocomplete="organization">', for_id="legal")}
        {_field("Billing email", '<input class="input" id="mail" type="email" value="accounts@kiln" autocomplete="email" aria-describedby="mail-e" aria-invalid="true">', error="Enter a full address, like accounts@kiln.example", for_id="mail")}
        {_field("VAT number", '<input class="input mono" id="vat" placeholder="GB 123 4567 89">', hint="Optional. Needed to invoice without VAT in the EU.", for_id="vat")}
        {_field("Country", '<select class="select" id="country"><option>United Kingdom</option><option>Ireland</option><option>Germany</option></select>', for_id="country")}
        <div class="wide">{_field("Billing address", '<textarea class="textarea" id="addr" style="min-height:84px">14 Foundry Lane, Stoke-on-Trent ST1 4AB</textarea>', for_id="addr")}</div>
      </div>
      <div class="actions" style="justify-content:space-between;margin-top:26px"><button class="btn" type="button">{icon("chevron").replace('class="ico"', 'class="ico" style="transform:scaleX(-1)"')}Back</button><button class="btn btn--primary" type="submit">Continue to review</button></div>
    </form>
    <aside class="card" aria-labelledby="sum"><h2 id="sum" style="margin-bottom:14px">Your order</h2>
      <ul class="list"><li>Business plan<b class="num" style="margin-left:auto">$24 × 8</b></li><li>Extra storage, 200 GB<b class="num" style="margin-left:auto">$10</b></li><li class="muted">14-day trial<span style="margin-left:auto">−$202</span></li></ul>
      <hr class="divider"><div style="display:flex;justify-content:space-between;align-items:baseline"><b>Due today</b><b class="num" style="font:600 1.7rem var(--font-display)">$0.00</b></div><p class="muted" style="font-size:.88rem;margin-top:8px">Then $202 per month from 1 April. Cancel any time before then.</p>
    </aside>
  </div>
</main>"""
    return Screen(
        "form-wizard",
        "Form: multi-step wizard",
        "A stepper with done, current and next steps, a card of billing fields with a visible error, plan choice cards, and an order summary beside it.",
        "paper",
        "dmserif",
        css + SPLIT,
        body,
        ["check", "chevron", "x"],
        ["calm", "guided", "light"],
        ["onboarding", "checkout", "registration", "applications", "setup"],
        "airy",
        uses="a task with several parts that people should finish in order: onboarding, checkout, applications, setup",
        tags=["form", "wizard", "stepper", "validation", "summary"],
    )


def line_entry() -> Screen:
    lines = [
        ("Brand workshop, two days", "2", "1,800.00"),
        ("Identity guidelines (PDF)", "1", "2,400.00"),
        ("Printed stationery set", "3", "310.00"),
    ]
    rows = "".join(
        f'<tr><td><input class="input" value="{d}" aria-label="Description"></td><td><input class="input num" style="width:76px;text-align:right" value="{q}" aria-label="Quantity"></td>'
        f'<td><input class="input num" style="width:120px;text-align:right" value="{p}" aria-label="Unit price"></td><td class="r num" style="width:130px"><b>${float(q) * float(p.replace(",", "")):,.2f}</b></td>'
        f'<td style="width:50px"><button class="btn btn--sm btn--ghost btn--icon" aria-label="Remove line">{icon("x")}</button></td></tr>'
        for d, q, p in lines
    )
    css = ".entry td{padding:8px 10px}.entry thead th{padding:10px}.totals{display:grid;gap:8px;max-width:320px;margin-left:auto}.totals div{display:flex;justify-content:space-between}"
    body = f"""
<div class="app">
{sidebar("Ledgerline", "L", [("home", "Overview", ""), ("file", "Invoices", "3"), ("users", "Clients", ""), ("card", "Payments", ""), ("chart", "Reports", "")], "Invoices", None, ("JR", "Jordan Reyes", "Studio owner"))}
<main class="main" style="max-width:1000px">
  <div class="top"><div><p class="muted mono">INV-0412 · Draft</p><h1>New invoice</h1></div><div class="actions"><button class="btn">Save draft</button><button class="btn">Preview</button><button class="btn btn--primary">{icon("send")}Send invoice</button></div></div>
  <form class="card" aria-label="Invoice" style="padding:26px">
    <div class="grid cols-3" style="gap:18px">
      {_field("Client", '<select class="select" id="client"><option>Hollis &amp; Park</option><option>Lumen Studio</option></select>', for_id="client")}
      {_field("Issue date", '<input class="input" id="issue" value="18 March 2025">', for_id="issue")}
      {_field("Due", '<select class="select" id="due"><option>In 14 days · 1 April</option><option>In 30 days</option></select>', for_id="due")}
    </div>
    <h2 style="margin:26px 0 10px;font-size:1rem">Lines</h2>
    <div class="table-wrap"><table class="entry"><thead><tr><th>Description</th><th class="r">Qty</th><th class="r">Unit price</th><th class="r">Amount</th><th><span class="sr">Remove</span></th></tr></thead><tbody>{rows}</tbody></table></div>
    <button class="btn btn--sm" type="button" style="margin-top:12px">{icon("plus")}Add a line</button>
    <hr class="divider" style="margin:24px 0">
    <div class="grid cols-2" style="gap:24px;align-items:start" id="split">
      {_field("Note to the client", '<textarea class="textarea" id="note">Thank you for a great project. Payment by bank transfer, details below.</textarea>', hint="Shown at the bottom of the invoice.", for_id="note")}
      <div class="totals"><div><span class="muted">Subtotal</span><b class="num">$8,730.00</b></div><div><span class="muted">VAT, 20%</span><b class="num">$1,746.00</b></div><hr class="divider" style="margin:4px 0"><div style="align-items:baseline"><b>Total due</b><b class="num" style="font:600 1.7rem var(--font-display)">$10,476.00</b></div></div>
    </div>
  </form>
</main></div>"""
    return Screen(
        "form-line-entry",
        "Form: invoice with line items",
        "A document-style data entry screen: header fields, an editable lines table with live amounts, notes and a totals block, with save, preview and send actions.",
        "slate",
        "inter",
        css + SPLIT,
        body,
        ["home", "file", "users", "card", "chart", "plus", "x", "send"],
        ["businesslike", "efficient", "light"],
        ["invoicing", "quotes", "orders", "expenses", "timesheets"],
        "balanced",
        uses="entering a document made of repeated lines: invoices, quotes, purchase orders, expense reports",
        tags=["form", "data entry", "line items", "totals", "side navigation"],
    )


def long_form() -> Screen:
    css = (
        ".sections{display:grid;gap:18px}.fs{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:28px;padding:26px;align-items:start}.fs h2{font-size:1.05rem}.fs>div:first-child p{margin-top:6px;color:var(--color-muted);font-size:.92rem}"
        ".fields{display:grid;gap:18px}.row2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.stickybar{margin-top:18px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius);padding:12px 16px;display:flex;gap:12px;justify-content:flex-end;align-items:center;flex-wrap:wrap}"
        "@media (max-width:900px){.fs,.row2{grid-template-columns:minmax(0,1fr)}}"
    )
    body = f"""
<div class="app">
{sidebar("Ward &amp; Co", "W", [("users", "Patients", ""), ("calendar", "Appointments", "6"), ("file", "Referrals", ""), ("inbox", "Messages", "2")], "Patients", None, ("EN", "Dr Elena Novak", "General practice"))}
<main class="main" style="max-width:980px">
  <div class="top"><div><h1>New patient registration</h1><p class="sub">Fields marked * are needed to book a first appointment.</p></div></div>
  <div role="alert" class="card" style="border-color:var(--color-danger);background:color-mix(in srgb,var(--color-danger) 7%,var(--color-surface));display:flex;gap:12px;align-items:flex-start;margin-bottom:18px"><span style="color:var(--color-danger)">{icon("x")}</span><div><b>2 fields need your attention</b><p class="muted" style="margin-top:2px"><a href="#dob">Date of birth</a> is not a valid date, and <a href="#phone">phone</a> needs a number we can reach.</p></div></div>
  <form class="sections" aria-label="Registration">
    <section class="card fs" aria-labelledby="s1"><div><h2 id="s1">About the patient</h2><p>As it appears on their ID. We use it on every letter.</p></div>
      <div class="fields"><div class="row2">{_field("First name *", '<input class="input" id="fn" value="Marcus" autocomplete="given-name">', for_id="fn")}{_field("Last name *", '<input class="input" id="ln" value="Adeyemi" autocomplete="family-name">', for_id="ln")}</div>
      <div class="row2">{_field("Date of birth *", '<input class="input" id="dob" value="31/02/1988" aria-invalid="true" aria-describedby="dob-e">', error="There is no 31 February. Use day, month, year.", for_id="dob")}{_field("Sex recorded at birth", '<select class="select" id="sex"><option>Male</option><option>Female</option><option>Prefer not to say</option></select>', for_id="sex")}</div></div></section>
    <section class="card fs" aria-labelledby="s2"><div><h2 id="s2">Contact</h2><p>For appointment reminders only.</p></div>
      <div class="fields"><div class="row2">{_field("Phone *", '<input class="input" id="phone" value="0121 4" type="tel" aria-invalid="true" aria-describedby="phone-e">', error="That number is too short.", for_id="phone")}{_field("Email", '<input class="input" id="em" type="email" placeholder="name@example.com">', for_id="em")}</div>
      {_field("Address", '<textarea class="textarea" id="ad" style="min-height:80px">52 Larch Road, Birmingham B13 9QA</textarea>', for_id="ad")}</div></section>
    <section class="card fs" aria-labelledby="s3"><div><h2 id="s3">Preferences</h2><p>You can change these at any time.</p></div>
      <div class="fields"><label class="check"><input type="checkbox" checked> Send reminders by text message</label><label class="check"><input type="checkbox"> Send reminders by email</label><label class="check"><input type="checkbox" checked> Share my record with my pharmacy</label></div></section>
  </form>
  <div class="stickybar"><!-- for a form taller than the screen add position:sticky;bottom:0 here --><span class="muted" style="margin-right:auto">Unsaved changes</span><button class="btn">Cancel</button><button class="btn btn--primary">Register patient</button></div>
</main></div>"""
    return Screen(
        "form-long",
        "Form: long page form with validation",
        "A long single-page form in titled sections (the heading and help on the left, the fields on the right), an error summary that links to each field, inline errors and a sticky action bar.",
        "harbour",
        "manrope",
        css,
        body,
        ["users", "calendar", "file", "inbox", "x"],
        ["clear", "trustworthy", "light"],
        ["healthcare", "registration", "applications", "hr", "government"],
        "airy",
        uses="a form with many fields that must be easy to scan and correct: registrations, applications, records",
        tags=["form", "validation", "error summary", "sections", "side navigation"],
    )


def sign_in() -> Screen:
    css = (
        ".auth{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);min-height:100vh}.auth-form{display:grid;align-content:center;justify-items:center;padding:clamp(24px,5vw,64px)}.auth-card{width:min(400px,100%);display:grid;gap:18px}"
        ".auth-art{background:var(--color-primary);color:var(--color-on-primary);padding:clamp(28px,5vw,64px);display:grid;align-content:space-between;position:relative}.art-clip{position:absolute;inset:0;overflow:hidden;pointer-events:none}.art-clip svg{position:absolute;right:-6%;top:12%;width:min(78%,560px);opacity:.95}"
        ".auth-art blockquote{margin:0;position:relative;max-width:30ch;font:500 clamp(1.4rem,2.6vw,2rem)/1.25 var(--font-display)}.auth-art cite{display:block;margin-top:14px;font:400 .95rem var(--font-body-md);opacity:.85}.auth-art .brand i{background:var(--color-on-primary);color:var(--color-primary)}"
        '.or{display:flex;align-items:center;gap:12px;color:var(--color-muted);font-size:.88rem}.or::before,.or::after{content:"";flex:1;height:1px;background:var(--color-border)}@media (max-width:860px){.auth{grid-template-columns:minmax(0,1fr)}.auth-art{display:none}}'
    )
    art = (
        '<svg viewBox="0 0 400 400" aria-hidden="true"><circle cx="270" cy="270" r="190" fill="none" stroke="currentColor" stroke-opacity=".22" stroke-width="2"/><circle cx="270" cy="270" r="140" fill="none" stroke="currentColor" stroke-opacity=".3" stroke-width="2"/>'
        '<circle cx="270" cy="270" r="90" fill="none" stroke="currentColor" stroke-opacity=".4" stroke-width="2"/><path d="M80 330c60-70 110-20 170-90s70-110 130-150" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><circle cx="380" cy="90" r="12" fill="currentColor"/></svg>'
    )
    body = f"""
<div class="auth">
  <main class="auth-form"><div class="auth-card">
    <div class="brand" style="padding:0 0 6px"><i>H</i>Harbourside</div>
    <div><h1>Welcome back</h1><p class="muted" style="margin-top:6px">Sign in to see this week's bookings.</p></div>
    <button class="btn" style="width:100%" type="button">{icon("shield")}Continue with company single sign-on</button>
    <div class="or">or use your email</div>
    <form style="display:grid;gap:16px" aria-label="Sign in">
      {_field("Email", '<input class="input" id="email" type="email" value="sam@harbourside.example" autocomplete="username">', for_id="email")}
      <div class="field"><div style="display:flex;justify-content:space-between"><label for="pw">Password</label><a href="#" style="font-size:.88rem">Forgot it?</a></div><input class="input" id="pw" type="password" value="correcthorse" autocomplete="current-password"></div>
      <label class="check"><input type="checkbox" checked> Keep me signed in on this device</label>
      <button class="btn btn--primary" style="width:100%;min-height:44px" type="submit">Sign in</button>
    </form>
    <p class="muted" style="text-align:center">New here? <a href="#">Create an account</a></p>
  </div></main>
  <aside class="auth-art"><div class="art-clip">{art}</div><div class="brand" style="padding:0;position:relative"><i>H</i>Harbourside</div><blockquote>"We stopped chasing spreadsheets on Mondays. The week simply appears."<cite>Dana Whitlock, operations manager at Pier 9 Charters</cite></blockquote></aside>
</div>"""
    return Screen(
        "form-sign-in",
        "Form: sign-in split screen",
        "A sign-in page split in two: the form (single sign-on, email, password, remember me) beside a colour panel with drawn contour art and a customer quote.",
        "harbour",
        "outfit",
        css,
        body,
        ["shield"],
        ["welcoming", "confident", "teal"],
        ["authentication", "saas", "marketplace", "booking", "portal"],
        "airy",
        uses="the door of an application: sign in, sign up, reset; the panel can carry the product's promise",
        tags=["form", "authentication", "split screen", "drawn art"],
    )


def quick_capture() -> Screen:
    css = (
        ".cap{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:18px;align-items:start}.kbd{font:600 .78rem var(--font-mono);border:1px solid var(--color-border);border-bottom-width:2px;border-radius:6px;padding:1px 6px;background:var(--color-surface);color:var(--color-muted)}"
        ".chips{display:flex;flex-wrap:wrap;gap:8px}.chip{border:1px solid var(--field);background:var(--color-surface);color:var(--color-ink);border-radius:999px;padding:5px 14px;font:600 .88rem var(--font-body-md);cursor:pointer}.chip[aria-pressed=true]{background:var(--color-primary);border-color:var(--color-primary);color:var(--color-on-primary)}"
        "@media (max-width:1000px){.cap{grid-template-columns:minmax(0,1fr)}}"
    )
    recent = [
        ("Pot of the day: cardamom bun", "Bakery", "09:41"),
        ("Delivery short by 2 trays", "Supplier", "09:12"),
        ("Oven 2 ran hot, reset", "Equipment", "08:50"),
        ("Allergen sign replaced", "Compliance", "08:15"),
    ]
    items = "".join(
        f'<li><div style="flex:1;min-width:0"><div>{t}</div><div class="muted" style="font-size:.85rem">{c}</div></div><span class="mono muted">{w}</span></li>'
        for t, c, w in recent
    )
    body = f"""
<header class="topbar"><div class="brand" style="padding:0"><i>D</i>Dayledger</div><nav aria-label="Primary"><a href="#" aria-current="page">Log</a><a href="#">Checklists</a><a href="#">Reports</a></nav><div class="grow"></div><span class="avatar">LM</span></header>
<main class="main" style="max-width:1040px;margin:0 auto">
  <div class="top"><div><h1>Shift log</h1><p class="sub">Riverside bakery · Tuesday morning shift</p></div></div>
  <div class="cap">
    <form class="card" aria-label="New entry" style="padding:24px;display:grid;gap:18px">
      <div class="field"><label for="what">What happened?</label><textarea class="textarea" id="what" style="min-height:120px" autofocus>Walk-in fridge reading 6.2 °C at 09:55, adjusted the thermostat.</textarea><p class="hint">Plain words are fine. Add a photo if it helps.</p></div>
      <div class="field"><span class="label">Category</span><div class="chips" role="group" aria-label="Category"><button type="button" class="chip" aria-pressed="false">Bakery</button><button type="button" class="chip" aria-pressed="false">Supplier</button><button type="button" class="chip" aria-pressed="true">Equipment</button><button type="button" class="chip" aria-pressed="false">Compliance</button><button type="button" class="chip" aria-pressed="false">Other</button></div></div>
      <div class="grid cols-2" style="gap:16px"><div class="field"><label for="reading">Reading</label><input class="input mono" id="reading" value="6.2 °C"></div><div class="field"><label for="who">Who is on it?</label><select class="select" id="who"><option>Me</option><option>Lucia Marin</option><option>Ops team</option></select></div></div>
      <div class="actions" style="justify-content:space-between"><span class="muted" style="font-size:.88rem"><span class="kbd">Ctrl</span> + <span class="kbd">Enter</span> to save</span><div class="actions"><button class="btn" type="button">{icon("plus")}Photo</button><button class="btn btn--primary" type="submit">Save entry</button></div></div>
    </form>
    <section class="card" aria-labelledby="rec"><div class="card-head"><h2 id="rec">Earlier today</h2><span class="pill pill--ok">4 logged</span></div><ul class="list">{items}</ul></section>
  </div>
</main>"""
    return Screen(
        "form-quick-capture",
        "Form: quick capture",
        "A fast entry form for frequent small records: one big text box, category chips, two short fields, a keyboard hint, and today's earlier entries beside it.",
        "paper",
        "outfit",
        css,
        body,
        ["plus"],
        ["friendly", "quick", "light"],
        ["field work", "logs", "hospitality", "operations", "notes"],
        "balanced",
        uses="something people do many times a day: a log entry, a note, a ticket, a check-in; fewer fields, big targets, keyboard shortcut",
        tags=["form", "data entry", "chips", "top navigation"],
    )


ALL = [wizard, line_entry, long_form, sign_in, quick_capture]
