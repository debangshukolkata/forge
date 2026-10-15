"""Web-application screens: inbox, chat, week calendar, customer record, map with a list, a document editor and a set of empty, error and loading states (D-366)."""

from __future__ import annotations

from .kit import icon, sidebar
from .screen import Screen

SPLIT = "@media (max-width:1000px){#split{grid-template-columns:minmax(0,1fr)!important}}"


def inbox() -> Screen:
    msgs = [
        (
            "Camille Roy",
            "Re: Venue contract, final draft",
            "Thanks, the changes look right. One last question about the cancellation clause: could we…",
            "09:42",
            True,
            True,
        ),
        (
            "Billing",
            "Your March invoice is ready",
            "Invoice INV-2025-03 for $432.00 is available to download.",
            "08:10",
            False,
            False,
        ),
        (
            "Devon Park",
            "Photos from Saturday",
            "Here is the folder with all 214 photos, sorted by room. The ones from the…",
            "Yesterday",
            False,
            False,
        ),
        (
            "Noura Haddad",
            "Quick question on the budget",
            "Do you have a minute tomorrow? I want to check the catering line before…",
            "Yesterday",
            True,
            False,
        ),
        (
            "Studio Loom",
            "Proofs for approval",
            "Attached are the three layouts we discussed. Option B uses the green…",
            "Mon",
            False,
            False,
        ),
    ]
    items = "".join(
        f'<li style="padding:0"><a href="#" style="display:block;width:100%;padding:14px 16px;text-decoration:none;color:inherit;{"background:var(--soft);box-shadow:inset 3px 0 0 var(--color-primary)" if sel else ""}"><div style="display:flex;justify-content:space-between;gap:10px"><b style="{"" if unread else "font-weight:500"}">{n}</b><span class="muted" style="font-size:.82rem;white-space:nowrap">{w}</span></div><div style="{"font-weight:600" if unread else ""}">{s}</div><div class="muted" style="font-size:.9rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{p}</div></a></li>'
        for n, s, p, w, unread, sel in msgs
    )
    css = (
        ".mail{display:grid;grid-template-columns:220px 360px minmax(0,1fr);min-height:100vh}.pane{border-right:1px solid var(--color-border);min-width:0}.mail-read{padding:clamp(18px,3vw,36px);max-width:760px}"
        ".folders a{display:flex;gap:10px;align-items:center;padding:8px 12px;border-radius:var(--r);color:var(--color-muted);text-decoration:none;font-weight:500}.folders a[aria-current=page]{background:var(--soft);color:var(--color-ink);font-weight:600}.folders .count{margin-left:auto}"
        "@media (max-width:1100px){.mail{grid-template-columns:200px minmax(0,1fr)}.mail-read{display:none}}@media (max-width:700px){.mail{grid-template-columns:minmax(0,1fr)}.folders{display:none}}"
    )
    body = f"""
<div class="mail">
  <nav class="pane folders" style="padding:16px 12px" aria-label="Folders"><div class="brand"><i>M</i>Mailroom</div><button class="btn btn--primary" style="width:100%;margin-bottom:14px">{icon("edit")}Compose</button>
    <a href="#" aria-current="page">{icon("inbox")}Inbox<span class="count">12</span></a><a href="#">{icon("star")}Starred</a><a href="#">{icon("send")}Sent</a><a href="#">{icon("file")}Drafts<span class="count">2</span></a><a href="#">{icon("trash")}Trash</a>
    <div class="nav-title">Labels</div><a href="#">{icon("tag")}Clients</a><a href="#">{icon("tag")}Venue</a><a href="#">{icon("tag")}Finance</a></nav>
  <section class="pane" style="background:var(--color-surface)" aria-label="Messages"><div style="padding:14px 16px;border-bottom:1px solid var(--color-border);display:flex;gap:10px;align-items:center"><div class="search" style="flex:1"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search mail" aria-label="Search mail"></div><button class="btn btn--icon" aria-label="Filter">{icon("filter")}</button></div><ul class="list">{items}</ul></section>
  <article class="mail-read" aria-labelledby="subj">
    <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:18px"><div class="actions"><button class="btn btn--sm">{icon("inbox")}Archive</button><button class="btn btn--sm">{icon("tag")}Label</button><button class="btn btn--sm btn--ghost btn--icon" aria-label="Delete">{icon("trash")}</button></div><span class="pill pill--info">Venue</span></div>
    <h1 id="subj" style="font-size:1.6rem">Re: Venue contract, final draft</h1>
    <div style="display:flex;gap:12px;align-items:center;margin:16px 0 20px"><span class="avatar" style="width:40px;height:40px">CR</span><div><b>Camille Roy</b> <span class="muted">&lt;camille@pier9.example&gt;</span><div class="muted" style="font-size:.88rem">To me · 9:42 today</div></div></div>
    <p style="margin-bottom:14px">Hi Sam,</p><p style="margin-bottom:14px">Thanks, the changes look right. One last question about the cancellation clause: could we move the free-cancellation window from 14 days to 21? Our guest list is not final until the end of the month.</p><p style="margin-bottom:14px">If that is fine on your side I will sign this afternoon and send the deposit tomorrow morning.</p><p>Best,<br>Camille</p>
    <div class="card" style="margin-top:26px;padding:14px"><div class="field"><label for="re" class="sr">Reply</label><textarea class="textarea" id="re" placeholder="Reply to Camille"></textarea></div><div class="actions" style="justify-content:space-between;margin-top:10px"><button class="btn btn--ghost btn--sm">{icon("plus")}Attach</button><button class="btn btn--primary">{icon("send")}Send</button></div></div>
  </article>
</div>"""
    return Screen(
        "inbox",
        "Inbox: three panes",
        "A mail-style inbox: folders and labels, a message list with unread emphasis and a selected row, and the open message with actions and an inline reply.",
        "slate",
        "inter",
        css,
        body,
        ["edit", "inbox", "star", "send", "file", "trash", "tag", "search", "filter", "plus"],
        ["productive", "familiar", "light"],
        ["email", "support", "messaging", "tickets", "case management"],
        "balanced",
        uses="work that arrives as messages or tickets: read, decide, answer; the three panes keep the list in view while reading",
        tags=["inbox", "three panes", "list", "reading pane"],
    )


def chat() -> Screen:
    threads = [
        ("Release planning", "Mara: Can we ship Thursday?", "10:21", True),
        ("Design review", "Eli: Updated the tokens", "09:50", False),
        ("Support rota", "You: Swapped with Joon", "Yesterday", False),
        ("Billing alerts", "Bot: Invoice 412 paid", "Yesterday", False),
    ]
    lis = "".join(
        f'<li style="padding:0"><a href="#" style="display:flex;gap:12px;align-items:center;width:100%;padding:12px 14px;text-decoration:none;color:inherit;{"background:var(--soft)" if sel else ""}"><span class="avatar">{n[0]}</span><div style="flex:1;min-width:0"><b>{n}</b><div class="muted" style="font-size:.88rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{p}</div></div><span class="muted" style="font-size:.8rem">{w}</span></a></li>'
        for n, p, w, sel in threads
    )
    css = (
        ".chat{display:grid;grid-template-columns:320px minmax(0,1fr);height:100vh}.chat-list{border-right:1px solid var(--color-border);background:var(--color-surface);overflow:auto}.thread{display:grid;grid-template-rows:auto minmax(0,1fr) auto;min-width:0}"
        ".msgs{overflow:auto;padding:24px clamp(16px,4vw,48px);display:grid;gap:14px;align-content:start}.bubble{max-width:min(560px,86%);padding:10px 14px;border-radius:16px;background:var(--color-surface);border:1px solid var(--color-border)}"
        ".me{justify-self:end;background:var(--color-primary);color:var(--color-on-primary);border-color:var(--color-primary)}.meta{font-size:.78rem;color:var(--color-muted);margin:0 4px 4px}.day{justify-self:center;font-size:.8rem;color:var(--color-muted)}"
        "@media (max-width:800px){.chat{grid-template-columns:minmax(0,1fr)}.chat-list{display:none}}"
    )
    body = f"""
<div class="chat">
  <aside class="chat-list" aria-label="Conversations"><div class="brand" style="padding:18px 16px 10px"><i>H</i>Huddle</div><div style="padding:6px 14px 12px"><div class="search"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search" aria-label="Search conversations"></div></div><ul class="list">{lis}</ul></aside>
  <section class="thread" aria-label="Release planning">
    <header style="display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px clamp(16px,4vw,48px);border-bottom:1px solid var(--color-border);background:var(--color-surface)"><div><h1 style="font-size:1.25rem">Release planning</h1><span class="muted" style="font-size:.88rem">5 members · 3 online</span></div><div class="actions"><button class="btn btn--icon btn--sm" aria-label="Search">{icon("search")}</button><button class="btn btn--icon btn--sm" aria-label="More">{icon("dots")}</button></div></header>
    <div class="msgs"><div class="day">Today</div>
      <div><div class="meta">Mara Chen · 10:14</div><div class="bubble">Regression run is green on staging. Only the invoice export is still flaky.</div></div>
      <div><div class="meta">Eli Brandt · 10:16</div><div class="bubble">I can take the export. Should be a small fix, it times out on large accounts.</div></div>
      <div style="justify-self:end"><div class="meta" style="text-align:right">You · 10:19</div><div class="bubble me">Great. If it lands by 3 we ship Thursday morning.</div></div>
      <div><div class="meta">Mara Chen · 10:21</div><div class="bubble">Can we ship Thursday? I would like support to have the notes by Wednesday noon.</div></div>
    </div>
    <form style="display:flex;gap:10px;align-items:flex-end;padding:14px clamp(16px,4vw,48px);border-top:1px solid var(--color-border);background:var(--color-surface)"><button type="button" class="btn btn--icon" aria-label="Attach a file">{icon("plus")}</button><div class="field" style="flex:1"><label class="sr" for="m">Message</label><textarea class="textarea" id="m" style="min-height:44px;height:44px" placeholder="Message the team"></textarea></div><button class="btn btn--primary" type="submit">{icon("send")}Send</button></form>
  </section>
</div>"""
    return Screen(
        "chat",
        "Chat: conversations and thread",
        "A team chat: a conversation list with previews and times, a thread with grouped bubbles, a day marker and your own messages in the accent, and a composer pinned to the bottom.",
        "ink",
        "grotesk",
        css,
        body,
        ["search", "dots", "plus", "send"],
        ["quick", "informal", "dark"],
        ["messaging", "collaboration", "community", "support chat", "assistant"],
        "balanced",
        uses="conversation: a thread of short messages with a composer; the same layout fits an assistant or a support chat",
        tags=["chat", "messages", "composer", "dark"],
    )


def calendar() -> Screen:
    days = ["Mon 17", "Tue 18", "Wed 19", "Thu 20", "Fri 21"]
    hours = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]
    events = [
        (0, 1, 2, "Standup", "var(--color-primary)"),
        (0, 3, 2, "Design crit", "var(--color-accent2)"),
        (1, 0, 1, "Planning", "var(--color-primary)"),
        (1, 4, 3, "Customer workshop", "var(--color-accent2)"),
        (2, 2, 2, "1:1 with Rosa", "var(--color-primary)"),
        (3, 1, 3, "Quarterly review", "var(--color-accent2)"),
        (4, 5, 2, "Demo day", "var(--color-primary)"),
    ]
    cols = ""
    for d, day in enumerate(days):
        cells = ""
        evs = "".join(
            f'<div class="ev" style="top:calc({s} * var(--row) + 3px);height:calc({span} * var(--row) - 6px);--c:{c}"><b>{t}</b><span>{hours[s]}</span></div>'
            for dd, s, span, t, c in events
            if dd == d
        )
        cols += f'<div class="daycol"><div class="dayhead"{" aria-current=date" if d == 1 else ""}>{day}</div><div class="slots">{cells}{evs}</div></div>'
    labels = "".join(f'<div class="hour">{h}</div>' for h in hours)
    css = (
        ".cal{--row:64px;display:grid;grid-template-columns:56px repeat(5,minmax(120px,1fr));border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-surface);overflow-x:auto}"
        ".hours{padding-top:45px}.hour{height:var(--row);font-size:.75rem;color:var(--color-muted);text-align:right;padding-right:10px;transform:translateY(-8px)}.daycol{border-left:1px solid var(--color-border);min-width:0}"
        ".dayhead{height:45px;display:grid;place-items:center;font-weight:600;border-bottom:1px solid var(--color-border)}.dayhead[aria-current=date]{color:var(--color-primary)}.slots{position:relative;height:calc(8 * var(--row));background:repeating-linear-gradient(to bottom,transparent 0,transparent calc(var(--row) - 1px),var(--color-border) calc(var(--row) - 1px),var(--color-border) var(--row))}"
        ".ev{position:absolute;left:6px;right:6px;border-radius:var(--r);padding:6px 10px;background:color-mix(in srgb,var(--c) 14%,var(--color-surface));border-left:4px solid var(--c);display:grid;align-content:start;overflow:hidden}.ev b{font-size:.88rem;color:var(--color-ink)}.ev span{font-size:.78rem;color:var(--color-muted)}"
        ".minical{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;font-size:.85rem}@media (max-width:480px){.minical{gap:4px;font-size:.75rem}}.minical span{padding:6px 0;border-radius:999px}.minical .dim{color:var(--color-muted)}.minical .on{background:var(--color-primary);color:var(--color-on-primary);font-weight:700}"
    )
    cells = (
        [(d, True) for d in range(24, 29)]
        + [(d, False) for d in range(1, 32)]
        + [(d, True) for d in range(1, 7)]
    )  # March 2025 starts on a Saturday
    mini = "".join(
        f'<span class="{"dim" if outside else ""}{" on" if not outside and d == 18 else ""}">{d}</span>'
        for d, outside in cells
    )
    body = f"""
<div class="app">
<aside class="side" aria-label="Calendar tools"><div class="brand"><i>C</i>Cadence</div><button class="btn btn--primary" style="margin-bottom:16px">{icon("plus")}New event</button>
<div class="label" style="padding:0 6px 8px;font-weight:600">March 2025</div><div class="minical" aria-hidden="true"><span class="dim">M</span><span class="dim">T</span><span class="dim">W</span><span class="dim">T</span><span class="dim">F</span><span class="dim">S</span><span class="dim">S</span>{mini}</div>
<div class="nav-title">Calendars</div><div style="display:grid;gap:10px;padding:0 10px"><label class="check"><input type="checkbox" checked> My calendar</label><label class="check"><input type="checkbox" checked> Design team</label><label class="check"><input type="checkbox"> Holidays</label></div></aside>
<main class="main"><div class="top"><div><h1>17–21 March</h1><p class="sub">Week 12 · 7 events</p></div><div class="actions"><div class="seg" role="group" aria-label="View"><button aria-pressed="false">Day</button><button aria-pressed="true">Week</button><button aria-pressed="false">Month</button></div><button class="btn btn--icon" aria-label="Previous week">{icon("chevron").replace('class="ico"', 'class="ico" style="transform:scaleX(-1)"')}</button><button class="btn btn--icon" aria-label="Next week">{icon("chevron")}</button></div></div>
<div class="cal"><div class="hours">{labels}</div>{cols}</div></main></div>"""
    return Screen(
        "calendar",
        "Calendar: week view",
        "A week calendar: a mini month and calendar toggles on the side, a time grid with positioned, colour-coded events, today's column marked and a Day, Week, Month switch.",
        "paper",
        "jakarta",
        css,
        body,
        ["plus", "chevron"],
        ["organised", "calm", "light"],
        ["scheduling", "booking", "planning", "team calendar", "appointments"],
        "balanced",
        uses="anything placed in time: meetings, appointments, shifts, bookings",
        tags=["calendar", "week view", "schedule", "side panel"],
    )


def record() -> Screen:
    timeline = [
        ("Call", "Discussed the renewal and the new seats", "Today, 11:20", "Amara Okafor"),
        ("Email", "Sent the updated quote (3 options)", "Mon 17 Mar", "Amara Okafor"),
        ("Note", "Prefers invoices in euros, billing contact changed to Lena", "Fri 14 Mar", "Hugo Ferreira"),
        ("Deal", "Moved to Negotiation", "Wed 12 Mar", "Amara Okafor"),
    ]
    tl = "".join(
        f'<li style="align-items:flex-start;gap:14px"><span class="pill pill--info" style="min-width:64px;justify-content:center">{k}</span><div><div>{t}</div><div class="muted" style="font-size:.85rem">{w} · {a}</div></div></li>'
        for k, t, w, a in timeline
    )
    body = f"""
<div class="app">
{sidebar("Compass", "C", [("home", "Home", ""), ("users", "Contacts", ""), ("layers", "Deals", "7"), ("calendar", "Activities", ""), ("chart", "Reports", "")], "Contacts", None, ("AO", "Amara Okafor", "Account executive"))}
<main class="main" style="max-width:1180px">
  <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:20px"><span class="avatar" style="width:72px;height:72px;font-size:1.4rem">AD</span><div style="flex:1;min-width:220px"><h1>Aster Dental Group</h1><p class="muted">12 clinics · Leeds, United Kingdom · Customer since 2022</p><div class="actions" style="margin-top:8px"><span class="pill pill--ok">Active</span><span class="pill pill--warn">Renewal in 41 days</span></div></div>
    <div class="actions"><button class="btn">{icon("mail")}Email</button><button class="btn">{icon("calendar")}Schedule</button><button class="btn btn--primary">{icon("edit")}Edit</button></div></div>
  <div class="tabs" role="tablist" style="margin-bottom:18px"><a href="#" aria-current="page">Overview</a><a href="#">Deals <span class="count" style="margin-left:4px">2</span></a><a href="#">Contacts <span class="count" style="margin-left:4px">5</span></a><a href="#">Files</a><a href="#">Billing</a></div>
  <div class="grid" style="grid-template-columns:minmax(0,2fr) minmax(0,1fr)" id="split">
    <div style="display:grid;gap:16px">
      <section class="card" aria-labelledby="tl"><div class="card-head"><h2 id="tl">Activity</h2><button class="btn btn--sm">{icon("plus")}Log activity</button></div><ul class="list">{tl}</ul></section>
      <section class="card" aria-labelledby="nt"><h2 id="nt" style="margin-bottom:10px">Add a note</h2><div class="field"><label class="sr" for="note">Note</label><textarea class="textarea" id="note" placeholder="What should the team know?"></textarea></div><div class="actions" style="justify-content:flex-end;margin-top:10px"><button class="btn btn--primary btn--sm">Save note</button></div></section>
    </div>
    <aside style="display:grid;gap:16px;align-content:start"><section class="card" aria-labelledby="dt"><h2 id="dt" style="margin-bottom:6px">Details</h2><dl style="margin:0;display:grid;gap:14px"><div><dt class="muted" style="font-size:.85rem">Annual value</dt><dd style="margin:0;font:600 1.5rem var(--font-display)" class="num">€84,000</dd></div><div><dt class="muted" style="font-size:.85rem">Owner</dt><dd style="margin:0">Amara Okafor</dd></div><div><dt class="muted" style="font-size:.85rem">Main contact</dt><dd style="margin:0">Lena Voss · lena@aster.example</dd></div><div><dt class="muted" style="font-size:.85rem">Plan</dt><dd style="margin:0">Business, 120 seats</dd></div></dl></section>
      <section class="card" aria-labelledby="hl"><h2 id="hl" style="margin-bottom:10px">Account health</h2><div class="meter" role="img" aria-label="Health 82 percent"><i style="width:82%"></i></div><p class="muted" style="margin-top:8px;font-size:.9rem">82 of 100. Logins up 14% this quarter.</p></section></aside>
  </div>
</main></div>"""
    return Screen(
        "record",
        "Record: customer profile",
        "A record page: identity header with status pills and actions, tabs, an activity timeline with a note box, and a side card of key details and account health.",
        "harbour",
        "dmserif",
        SPLIT,
        body,
        ["home", "users", "layers", "calendar", "chart", "mail", "edit", "plus"],
        ["considered", "calm", "light"],
        ["crm", "customers", "patients", "accounts", "candidates"],
        "balanced",
        uses="everything known about one entity: a customer, a patient, a candidate, an asset; the header, tabs, timeline and facts are the pattern",
        tags=["record", "profile", "timeline", "tabs", "side navigation"],
    )


def map_list() -> Screen:
    places = [
        ("Riverside Depot", "1.2 km · open until 20:00", "ok", "Open"),
        ("Market Street Hub", "2.4 km · closes in 40 min", "warn", "Closing"),
        ("North Gate Locker", "3.1 km · 24 hours", "ok", "Open"),
        ("Harbour Pickup", "4.8 km · opens 08:00", "danger", "Closed"),
    ]
    lis = "".join(
        f'<li style="padding:0"><a href="#" style="display:flex;gap:12px;align-items:center;width:100%;padding:14px 16px;text-decoration:none;color:inherit;{"background:var(--soft)" if i == 0 else ""}"><span class="avatar" style="background:var(--color-primary);color:var(--color-on-primary)">{i + 1}</span><div style="flex:1;min-width:0"><b>{n}</b><div class="muted" style="font-size:.88rem">{d}</div></div><span class="pill pill--{t}">{s}</span></a></li>'
        for i, (n, d, t, s) in enumerate(places)
    )
    pins = [(34, 40, 1), (58, 28, 2), (72, 62, 3), (26, 70, 4)]
    pin_html = "".join(
        f'<g transform="translate({x * 8},{y * 5})"><path d="M0 0c-14-18-20-26-20-36a20 20 0 1 1 40 0c0 10-6 18-20 36z" transform="translate(0,34)" fill="{"var(--color-accent2)" if n == 1 else "var(--color-primary)"}" stroke="var(--color-surface)" stroke-width="3"/><circle cx="0" cy="-2" r="7" fill="var(--color-surface)"/></g>'
        for x, y, n in pins
    )
    mapsvg = (
        '<svg viewBox="0 0 800 500" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Map of the city with four pickup points" style="position:absolute;inset:0;width:100%;height:100%">'
        '<rect width="800" height="500" fill="color-mix(in srgb,var(--color-primary) 6%,var(--color-neutral))"/>'
        '<path d="M-20 360c120-40 200 30 330-10s210-90 300-60 140 30 190 0V520H-20z" fill="color-mix(in srgb,var(--color-primary) 22%,var(--color-neutral))"/>'
        '<g fill="color-mix(in srgb,var(--color-ink) 7%,var(--color-neutral))"><rect x="60" y="50" width="120" height="70" rx="6"/><rect x="200" y="50" width="90" height="70" rx="6"/><rect x="320" y="40" width="150" height="80" rx="6"/><rect x="500" y="50" width="110" height="70" rx="6"/><rect x="640" y="40" width="120" height="90" rx="6"/>'
        '<rect x="60" y="150" width="120" height="80" rx="6"/><rect x="200" y="150" width="90" height="80" rx="6"/><rect x="320" y="150" width="150" height="70" rx="6"/><rect x="500" y="150" width="110" height="80" rx="6"/><rect x="640" y="160" width="120" height="70" rx="6"/></g>'
        '<g stroke="var(--color-surface)" stroke-width="10" fill="none" stroke-linecap="round"><path d="M0 130H800"/><path d="M190 0V330"/><path d="M310 0V300"/><path d="M485 0V310"/><path d="M625 0V300"/><path d="M0 240C200 250 500 230 800 250"/></g>'
        f"<g>{pin_html}</g></svg>"
    )
    css = ".mapwrap{position:relative;min-height:560px;border-radius:var(--radius);overflow:hidden;border:1px solid var(--color-border)}.mapctl{position:absolute;right:14px;top:14px;display:grid;gap:8px}"
    body = f"""
<header class="topbar"><div class="brand" style="padding:0"><i>P</i>Parcelpoint</div><nav aria-label="Primary"><a href="#">Track</a><a href="#" aria-current="page">Find a point</a><a href="#">Send</a></nav><div class="grow"></div><span class="avatar">NA</span></header>
<main class="main" style="max-width:1240px;margin:0 auto">
  <div class="top"><div><h1>Find a pickup point</h1><p class="sub">Near 14 Foundry Lane · 4 points within 5 km</p></div><div class="actions"><div class="search" style="width:min(280px,70vw)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" value="14 Foundry Lane" aria-label="Address"></div><button class="btn">{icon("filter")}Open now</button></div></div>
  <div class="grid" style="grid-template-columns:minmax(300px,380px) minmax(0,1fr)" id="split">
    <section class="card" style="padding:0;overflow:hidden;align-self:start" aria-label="Pickup points"><ul class="list">{lis}</ul></section>
    <div class="mapwrap">{mapsvg}<div class="mapctl"><button class="btn btn--icon" aria-label="Zoom in">{icon("plus")}</button><button class="btn btn--icon" aria-label="My location">{icon("map")}</button></div>
    <div class="card" style="position:absolute;left:14px;bottom:14px;right:14px;max-width:420px;padding:14px 16px"><div style="display:flex;justify-content:space-between;gap:10px"><div><b>1 · Riverside Depot</b><div class="muted" style="font-size:.88rem">22 Mill Quay · open until 20:00</div></div><span class="pill pill--ok">Open</span></div><div class="actions" style="margin-top:12px"><button class="btn btn--primary btn--sm">Choose this point</button><button class="btn btn--sm">Directions</button></div></div></div>
  </div>
</main>"""
    return Screen(
        "map-list",
        "Map: list and map side by side",
        "A locator: a result list with status pills beside a drawn map with numbered pins, zoom controls and a detail card for the selected place.",
        "slate",
        "outfit",
        css + SPLIT,
        body,
        ["search", "filter", "plus", "map"],
        ["clear", "practical", "light"],
        ["logistics", "store locator", "delivery", "real estate", "field service"],
        "balanced",
        uses="choosing a place: stores, pickup points, listings, jobs; the list and the map stay in step",
        tags=["map", "list", "locator", "drawn svg map", "top navigation"],
    )


def editor() -> Screen:
    body = f"""
<div class="app doc">
<aside class="side" aria-label="Document outline"><div class="brand"><i>Q</i>Quill</div><button class="btn btn--sm" style="margin-bottom:10px">{icon("plus")}New page</button>
<div class="nav-title">Project handbook</div><div class="nav"><a href="#">{icon("file")}Welcome</a><a href="#" aria-current="page">{icon("file")}Launch checklist</a><a href="#">{icon("file")}Roles</a><a href="#">{icon("file")}Incident response</a><a href="#">{icon("file")}Glossary</a></div>
<div class="nav-title">On this page</div><div class="nav"><a href="#" style="padding-left:24px">Before launch</a><a href="#" style="padding-left:24px">Launch day</a><a href="#" style="padding-left:24px">After launch</a></div></aside>
<main style="display:grid;grid-template-columns:minmax(0,1fr) 300px;min-width:0" id="split">
  <article style="padding:clamp(20px,4vw,56px);max-width:780px;margin:0 auto;min-width:0;width:100%"><div class="actions" style="margin-bottom:22px;gap:4px;border:1px solid var(--color-border);border-radius:var(--r);padding:4px;background:var(--color-surface);width:fit-content"><button class="btn btn--sm btn--ghost btn--icon" aria-label="Bold"><b>B</b></button><button class="btn btn--sm btn--ghost btn--icon" aria-label="Italic"><i>I</i></button><button class="btn btn--sm btn--ghost btn--icon" aria-label="Link">{icon("link")}</button><button class="btn btn--sm btn--ghost btn--icon" aria-label="Checklist">{icon("check")}</button></div>
    <p class="muted" style="font-size:.88rem">Edited 6 minutes ago by Rosa Kim</p>
    <h1 style="font-size:2.4rem;margin:6px 0 16px" contenteditable="true" spellcheck="false">Launch checklist</h1>
    <p style="font-size:1.08rem;line-height:1.7;color:var(--color-muted);margin-bottom:26px">Everything that has to be true before we say yes to a release. Owners are named; nothing here is optional unless it says so.</p>
    <h2 style="font-size:1.35rem;margin:26px 0 12px">Before launch</h2>
    <ul class="list" style="font-size:1.02rem"><li><label class="check"><input type="checkbox" checked> Release notes reviewed by support</label></li><li><label class="check"><input type="checkbox" checked> Rollback tested on staging</label></li><li><label class="check"><input type="checkbox"> Status page message drafted</label></li><li><label class="check"><input type="checkbox"> On-call rota confirmed for the weekend</label></li></ul>
    <h2 style="font-size:1.35rem;margin:26px 0 12px">Launch day</h2><p style="line-height:1.7;max-width:62ch">Announce in the release channel at 09:30. Keep the dashboard open, and pause the rollout at 5% for thirty minutes before widening it.</p></article>
  <aside style="border-left:1px solid var(--color-border);background:var(--color-surface);padding:20px 18px;display:grid;gap:16px;align-content:start" aria-label="Comments"><div class="card-head" style="margin:0"><h2>Comments</h2><span class="pill pill--info">2 open</span></div>
    <div class="card" style="padding:14px"><div style="display:flex;gap:10px;align-items:center;margin-bottom:6px"><span class="avatar" style="width:26px;height:26px;font-size:.75rem">MC</span><b>Mara Chen</b><span class="muted" style="font-size:.8rem">10:02</span></div><p style="font-size:.92rem">Who owns the status page? Name them here.</p><div class="actions" style="margin-top:10px"><button class="btn btn--sm">Reply</button><button class="btn btn--sm btn--ghost">Resolve</button></div></div>
    <div class="card" style="padding:14px"><div style="display:flex;gap:10px;align-items:center;margin-bottom:6px"><span class="avatar" style="width:26px;height:26px;font-size:.75rem">EB</span><b>Eli Brandt</b><span class="muted" style="font-size:.8rem">Yesterday</span></div><p style="font-size:.92rem">Thirty minutes at 5% feels long. Fifteen?</p><div class="actions" style="margin-top:10px"><button class="btn btn--sm">Reply</button><button class="btn btn--sm btn--ghost">Resolve</button></div></div></aside>
</main></div>"""
    css = ".app.doc{grid-template-columns:260px minmax(0,1fr)}@media (max-width:860px){.app.doc{grid-template-columns:minmax(0,1fr)}}@media (max-width:1100px){#split{grid-template-columns:minmax(0,1fr)!important}#split>aside{border-left:0;border-top:1px solid var(--color-border)}}"
    return Screen(
        "editor",
        "Editor: document with outline and comments",
        "A writing surface: a page tree and an on-this-page outline, a formatting bar, a large editable title, checklist items, and a comments column with open threads.",
        "paper",
        "dmserif",
        css,
        body,
        ["plus", "file", "link", "check"],
        ["quiet", "focused", "light"],
        ["documents", "wiki", "notes", "knowledge base", "handbook"],
        "airy",
        uses="writing and reviewing long content: documents, wikis, runbooks; the page stays wide and calm, tools sit at the edges",
        tags=["editor", "document", "comments", "outline"],
    )


def states() -> Screen:
    def card(icon_name: str, title: str, text: str, action: str, tone: str = "") -> str:
        return f'<section class="card state"><span class="badge {tone}">{icon(icon_name)}</span><h2>{title}</h2><p class="muted">{text}</p>{action}</section>'

    skeleton = '<section class="card state" aria-label="Loading" aria-busy="true"><div class="sk" style="width:46%"></div><div class="sk" style="width:90%;margin-top:18px"></div><div class="sk" style="width:80%"></div><div class="sk" style="width:62%"></div><div class="sk" style="height:84px;margin-top:18px"></div></section>'
    body = f"""
<header class="topbar"><div class="brand" style="padding:0"><i>L</i>Ledgerline</div><nav aria-label="Primary"><a href="#" aria-current="page">Invoices</a><a href="#">Clients</a><a href="#">Reports</a></nav><div class="grow"></div><span class="avatar">JR</span></header>
<main class="main" style="max-width:1120px;margin:0 auto;padding-top:34px">
  <div class="top"><div><h1>Empty, error and loading states</h1><p class="sub">Every screen has a moment with no data. Say what happened and offer the next step.</p></div></div>
  <div class="grid cols-3" style="gap:18px">
    {card("inbox", "No invoices yet", "When you send your first invoice it will appear here, with its status and payments.", f'<a class="btn btn--primary" href="#">{icon("plus")}Create an invoice</a>')}
    {card("search", "Nothing matches “harbor”", "Check the spelling or try fewer words. Filters are still on: status Paid, 2025.", '<button class="btn">Clear filters</button>')}
    {card("x", "We could not load your projects", "The request timed out. Your work is safe. This usually clears in a minute.", '<div class="actions" style="justify-content:center"><button class="btn btn--primary">Try again</button><a class="btn btn--ghost" href="#">Status page</a></div>', "badge--danger")}
    {card("bell", "You are offline", "Changes are saved on this device and will sync when you reconnect. 3 waiting.", '<span class="pill pill--warn">Sync paused</span>', "badge--warn")}
    {skeleton}
    {card("check", "All caught up", "You answered every message. New ones will show up here the moment they arrive.", '<span class="pill pill--ok">Inbox zero</span>', "badge--ok")}
  </div>
  <section class="card" style="margin-top:18px" aria-labelledby="ob"><div class="card-head"><div><h2 id="ob">Get started: 2 of 4 done</h2><p>The fastest way to see your first report.</p></div><div class="meter" style="width:160px" role="img" aria-label="50 percent"><i style="width:50%"></i></div></div>
    <ul class="list"><li><span class="badge badge--ok sm">{icon("check")}</span><div style="flex:1"><b>Create your workspace</b></div><span class="muted">Done</span></li><li><span class="badge badge--ok sm">{icon("check")}</span><div style="flex:1"><b>Invite a teammate</b></div><span class="muted">Done</span></li><li><span class="badge sm">3</span><div style="flex:1"><b>Connect your data</b><div class="muted" style="font-size:.88rem">Upload a CSV or link your account. Takes about two minutes.</div></div><button class="btn btn--primary btn--sm">Connect</button></li><li><span class="badge sm">4</span><div style="flex:1"><b>Open your first report</b></div><span class="muted">Locked</span></li></ul></section>
</main>"""
    css = (
        ".state{display:grid;justify-items:center;text-align:center;gap:10px;padding:32px 22px;align-content:center;min-height:240px}.state h2{font-size:1.1rem}.state p{max-width:34ch}"
        ".badge{width:52px;height:52px;border-radius:999px;display:grid;place-items:center;background:var(--soft);color:var(--color-primary);padding:1px;flex:none}.badge .ico{width:24px;height:24px}.badge--danger{background:color-mix(in srgb,var(--color-danger) 13%,var(--color-surface));color:var(--color-danger)}"
        ".badge--warn{background:color-mix(in srgb,var(--color-warn) 15%,var(--color-surface));color:var(--color-warn)}.badge--ok{background:color-mix(in srgb,var(--color-ok) 14%,var(--color-surface));color:var(--color-ok)}.badge.sm{width:30px;height:30px;font-size:.85rem;font-weight:700}.badge.sm .ico{width:16px;height:16px}"
        ".sk{height:14px;border-radius:6px;background:linear-gradient(90deg,var(--hover),color-mix(in srgb,var(--color-ink) 10%,var(--color-surface)),var(--hover));background-size:200% 100%;animation:sk 1.4s linear infinite;margin-top:12px}@keyframes sk{to{background-position:-200% 0}}"
    )
    return Screen(
        "empty-states",
        "States: empty, no results, error, offline, loading and first run",
        "Six state cards (empty list, no search results, load error, offline, skeleton loading, all caught up) and a first-run checklist with progress, so every moment without data has a next step.",
        "mono",
        "archivo",
        css,
        body,
        ["inbox", "search", "x", "bell", "check", "plus"],
        ["helpful", "plain", "light"],
        ["any app", "saas", "onboarding", "error handling"],
        "airy",
        uses="the screens people see when there is nothing to show or something went wrong: copy them into every list, search and fetch",
        tags=["empty state", "error", "loading", "skeleton", "onboarding"],
    )


ALL = [inbox, chat, calendar, record, map_list, editor, states]
