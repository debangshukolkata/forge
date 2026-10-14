"""Four screens built around records: a filterable table with bulk actions, master and detail, a kanban board and an editable grid (D-366)."""

from __future__ import annotations

from .kit import icon, sidebar
from .screen import Screen

SPLIT = "@media (max-width:1100px){#split{grid-template-columns:minmax(0,1fr)!important}}"


def data_table() -> Screen:
    people = [
        ("Amara Okafor", "amara@brightwell.io", "Design", "Admin", "ok", "Active", "2 min ago"),
        ("Luca Ferrante", "luca@brightwell.io", "Engineering", "Editor", "ok", "Active", "1 h ago"),
        ("Hana Takeda", "hana@brightwell.io", "Engineering", "Editor", "warn", "Invited", "Never"),
        ("Soren Lindqvist", "soren@brightwell.io", "Finance", "Viewer", "ok", "Active", "Yesterday"),
        ("Ines Duarte", "ines@brightwell.io", "Support", "Editor", "danger", "Suspended", "9 days ago"),
        ("Tomasz Wrona", "tomasz@brightwell.io", "Sales", "Viewer", "ok", "Active", "3 h ago"),
        ("Noor Haddad", "noor@brightwell.io", "Design", "Editor", "ok", "Active", "Today"),
    ]
    rows = ""
    for i, (name, email, team, role, tone, state, seen) in enumerate(people):
        checked = " checked" if i in (1, 5) else ""
        initials = "".join(part[0] for part in name.split())
        rows += (
            f'<tr><td style="width:44px"><label class="check"><input type="checkbox"{checked} aria-label="Select {name}"></label></td>'
            f'<td><div class="cell-main"><span class="avatar">{initials}</span><div><b>{name}</b><span>{email}</span></div></div></td>'
            f'<td>{team}</td><td>{role}</td><td><span class="pill pill--{tone}">{state}</span></td><td class="muted">{seen}</td>'
            f'<td class="r"><button class="btn btn--sm btn--ghost btn--icon" aria-label="Actions for {name}">{icon("dots")}</button></td></tr>'
        )
    body = f"""
<header class="topbar"><div class="brand" style="padding:0"><i>B</i>Brightwell</div>
<nav aria-label="Primary"><a href="#">Projects</a><a href="#" aria-current="page">People</a><a href="#">Billing</a><a href="#">Audit log</a></nav><div class="grow"></div><span class="avatar">AO</span></header>
<main class="main" style="max-width:1240px;margin:0 auto">
  <div class="top"><div><h1>People</h1><p class="sub">42 members in 6 teams · 3 invitations waiting</p></div><div class="actions"><button class="btn">{icon("download")}Export CSV</button><button class="btn btn--primary">{icon("plus")}Invite people</button></div></div>
  <div class="actions" style="margin-bottom:14px;justify-content:space-between">
    <div class="actions"><div class="search" style="width:min(300px,70vw)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search by name or email" aria-label="Search people"></div>
      <div class="seg" role="group" aria-label="Status"><button aria-pressed="true">All</button><button aria-pressed="false">Active</button><button aria-pressed="false">Invited</button><button aria-pressed="false">Suspended</button></div></div>
    <button class="btn">{icon("filter")}Team: all</button></div>
  <div class="card" style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:10px 16px;margin-bottom:12px;background:var(--soft)"><b>2 selected</b><button class="btn btn--sm">Change role</button><button class="btn btn--sm">Move to team</button><button class="btn btn--sm btn--danger">Suspend</button><button class="btn btn--sm btn--ghost" style="margin-left:auto">Clear</button></div>
  <div class="table-wrap"><table><thead><tr><th><label class="check"><input type="checkbox" aria-label="Select all"></label></th><th><button>Name {icon("down")}</button></th><th>Team</th><th>Role</th><th>Status</th><th>Last seen</th><th class="r"><span class="sr">Actions</span></th></tr></thead><tbody>{rows}</tbody></table></div>
  <div class="pager"><span>Showing 1–7 of 42</span><div class="actions"><button class="btn btn--sm" disabled>Previous</button><button class="btn btn--sm">Next</button></div></div>
</main>"""
    return Screen(
        "table-data", "Table: people with filters and bulk actions", "A full data table: search, status segments, a bulk-action bar for selected rows, avatars, status pills, row actions and pagination.",
        "mono", "archivo", SPLIT, body, ["search", "filter", "plus", "download", "dots", "down"], ["precise", "plain", "light"], ["admin", "team management", "saas", "hr", "back office"], "balanced",
        uses="any list of records people manage in bulk: users, customers, orders, assets; the table, its filters and the bulk bar are the pattern",
        tags=["table", "filters", "bulk actions", "pagination", "top navigation"],
    )


def master_detail() -> Screen:
    orders = [
        ("PO-1184", "Alder &amp; Finch Packaging", "$12,480", "warn", "In review", True),
        ("PO-1183", "Kestrel Components", "$3,915", "ok", "Approved", False),
        ("PO-1182", "Marlow Office Supply", "$864", "ok", "Approved", False),
        ("PO-1181", "Tern Logistics", "$7,200", "danger", "Rejected", False),
        ("PO-1180", "Alder &amp; Finch Packaging", "$5,640", "info", "Draft", False),
    ]
    items = "".join(
        f'<li style="padding:0"><a href="#" style="display:flex;gap:12px;align-items:center;width:100%;padding:12px 14px;text-decoration:none;color:inherit;{"background:var(--soft);box-shadow:inset 3px 0 0 var(--color-primary)" if sel else ""}"><div style="flex:1;min-width:0"><b class="mono" style="font-size:.88rem">{n}</b><div class="muted" style="font-size:.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{v}</div></div><div style="text-align:right"><b class="num">{a}</b><div><span class="pill pill--{t}">{s}</span></div></div></a></li>'
        for n, v, a, t, s, sel in orders
    )
    lines = [("Corrugated mailer, 300 × 220 mm", "4,000", "$1.24", "$4,960.00"), ("Kraft tape, 48 mm × 100 m", "600", "$2.10", "$1,260.00"), ("Custom tissue, one colour", "8,000", "$0.78", "$6,240.00")]
    rows = "".join(f'<tr><td>{d}</td><td class="r num">{q}</td><td class="r num">{p}</td><td class="r num"><b>{t}</b></td></tr>' for d, q, p, t in lines)
    events = [("Priya Nair submitted for review", "Today, 09:12"), ("Budget check passed: Packaging, Q2", "Today, 09:12"), ("Draft created by Priya Nair", "Yesterday, 17:40")]
    timeline = "".join(f'<li style="gap:14px;align-items:flex-start"><span class="avatar" style="width:10px;height:10px;margin-top:8px;padding:0;background:var(--color-primary)"></span><div><div>{e}</div><div class="muted" style="font-size:.85rem">{w}</div></div></li>' for e, w in events)
    body = f"""
<div class="app">
{sidebar("Procura", "P", [("inbox", "Approvals", "4"), ("file", "Purchase orders", ""), ("users", "Suppliers", ""), ("chart", "Spend", "")], "Purchase orders", None, ("DK", "Dana Kowalski", "Procurement"))}
<main class="main" style="padding-top:20px">
  <div class="top"><div><h1>Purchase orders</h1><p class="sub">12 open · $48,310 awaiting approval</p></div><button class="btn btn--primary">{icon("plus")}New order</button></div>
  <div class="grid" style="grid-template-columns:minmax(260px,340px) minmax(0,1fr);align-items:start" id="split">
    <section class="card" style="padding:0;overflow:hidden" aria-label="Orders"><div style="padding:12px 14px;border-bottom:1px solid var(--color-border)"><div class="search"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search orders" aria-label="Search orders"></div></div><ul class="list">{items}</ul></section>
    <section class="card" aria-labelledby="po">
      <div class="card-head" style="align-items:flex-start"><div><p class="mono muted">PO-1184 · Raised 12 March</p><h2 id="po" style="font-size:1.35rem;margin-top:4px">Alder &amp; Finch Packaging</h2></div><span class="pill pill--warn">In review</span></div>
      <div class="tabs" role="tablist" style="margin-bottom:18px"><a href="#" aria-current="page">Lines</a><a href="#">Approvals</a><a href="#">Documents</a><a href="#">History</a></div>
      <div class="grid cols-3" style="margin-bottom:18px"><div><div class="label muted">Total</div><b class="num" style="font:600 1.4rem var(--font-display)">$12,480.00</b></div><div><div class="label muted">Budget left</div><b class="num" style="font:600 1.4rem var(--font-display)">$21,900</b></div><div><div class="label muted">Delivery</div><b style="font:600 1.4rem var(--font-display)">28 March</b></div></div>
      <div class="table-wrap"><table><thead><tr><th>Item</th><th class="r">Qty</th><th class="r">Unit</th><th class="r">Total</th></tr></thead><tbody>{rows}</tbody></table></div>
      <h3 style="margin:22px 0 4px">Activity</h3><ul class="list">{timeline}</ul>
      <div class="actions" style="margin-top:18px;justify-content:flex-end"><button class="btn btn--danger">Reject</button><button class="btn">Ask a question</button><button class="btn btn--primary">{icon("check")}Approve</button></div>
    </section>
  </div>
</main></div>"""
    return Screen(
        "table-master-detail", "Table: master and detail", "A list on the left and the selected record on the right: header, tabs, key figures, line items, activity and decision buttons.",
        "slate", "jakarta", SPLIT, body, ["inbox", "file", "users", "chart", "search", "plus", "check"], ["businesslike", "calm", "light"], ["procurement", "approvals", "support", "crm", "orders"], "balanced",
        uses="work where someone moves through many records and acts on each: approvals, tickets, orders, candidates",
        tags=["list", "detail", "tabs", "side navigation", "line items"],
    )


def kanban() -> Screen:
    columns = [
        ("To do", "4", [("Draft the onboarding checklist", "Docs", "warn", "Mar 20", "RK"), ("Audit empty states", "Design", "info", "Mar 21", "AO"), ("Pick a status page vendor", "Ops", "", "Mar 25", "JM"), ("Write the March changelog", "Docs", "warn", "Mar 26", "RK")]),
        ("In progress", "3", [("Rebuild the invoice export", "Billing", "info", "Mar 19", "LF"), ("Fix timezone in reminders", "Bug", "danger", "Today", "HT"), ("Customer interviews, round 2", "Research", "", "Mar 22", "NH")]),
        ("In review", "2", [("Permissions model v2", "Platform", "info", "Mar 18", "SL"), ("Refund email copy", "Docs", "warn", "Mar 19", "RK")]),
        ("Done", "3", [("Rate limit the public API", "Platform", "ok", "Mar 14", "SL"), ("Retire the old dashboard", "Design", "ok", "Mar 13", "AO"), ("SSO for Business plan", "Platform", "ok", "Mar 11", "TW")]),
    ]
    tone = {"warn": "pill--warn", "info": "pill--info", "danger": "pill--danger", "ok": "pill--ok", "": ""}
    cols = ""
    for title, count, cards in columns:
        items = "".join(
            f'<article class="card" style="padding:14px;box-shadow:var(--shadow)"><span class="pill {tone[t]}" style="margin-bottom:8px">{label}</span><p style="font-weight:600;margin-bottom:12px">{text}</p><div style="display:flex;justify-content:space-between;align-items:center"><span class="muted" style="font-size:.85rem;display:inline-flex;gap:6px;align-items:center">{icon("calendar")}{due}</span><span class="avatar" style="width:28px;height:28px">{who}</span></div></article>'
            for text, label, t, due, who in cards
        )
        cols += f'<section class="lane" aria-label="{title}"><header><h2>{title}</h2><span class="count">{count}</span></header><div class="stack">{items}</div><button class="btn btn--ghost btn--sm" style="justify-content:flex-start">{icon("plus")}Add a card</button></section>'
    css = (
        ".board{display:grid;grid-template-columns:repeat(4,minmax(214px,1fr));gap:16px;align-items:start;overflow-x:auto;padding-bottom:8px}"
        ".lane{background:color-mix(in srgb,var(--color-ink) 4%,var(--color-neutral));border:1px solid var(--color-border);border-radius:var(--radius);padding:12px;display:grid;gap:10px}"
        ".lane header{display:flex;align-items:center;gap:8px;padding:2px 4px}.lane header h2{font-size:.95rem}.lane .count{font-size:.8rem;color:var(--color-muted);background:var(--color-surface);border:1px solid var(--color-border);border-radius:999px;padding:0 8px}"
        ".stack{display:grid;gap:10px}"
    )
    body = f"""
<div class="app">
{sidebar("Waypoint", "W", [("grid", "Board", ""), ("calendar", "Timeline", ""), ("chart", "Reports", ""), ("users", "Team", "")], "Board", [("Projects", [("tag", "Website relaunch", ""), ("tag", "Mobile app", ""), ("tag", "Billing", "")])], ("RK", "Rosa Kim", "Product manager"))}
<main class="main">
  <div class="top"><div><h1>Website relaunch</h1><p class="sub">Sprint 14 · 12 cards · ends Friday</p></div><div class="actions"><div class="search" style="width:min(240px,60vw)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Filter cards" aria-label="Filter cards"></div><button class="btn">{icon("filter")}Assignee</button><button class="btn btn--primary">{icon("plus")}New card</button></div></div>
  <div class="board">{cols}</div>
</main></div>"""
    return Screen(
        "table-kanban", "Board: kanban lanes", "A kanban board with four lanes, labelled cards with due dates and assignees, lane counts and add-card buttons; the lanes scroll sideways inside their frame on a phone.",
        "paper", "jakarta", css, body, ["grid", "calendar", "chart", "users", "tag", "search", "filter", "plus"], ["warm", "organised", "light"], ["project management", "tasks", "workflow", "recruiting", "support"], "balanced",
        uses="work that moves through stages: tasks, candidates, deals, tickets",
        tags=["board", "kanban", "cards", "side navigation"],
    )


def editable_grid() -> Screen:
    stock = [
        ("BX-2210", "Oat milk, 1 L", "Cold store A", 240, 120, "ok", "Healthy"),
        ("BX-2214", "Sourdough loaf", "Bakery rack", 36, 60, "danger", "Reorder now"),
        ("BX-2218", "Cultured butter, 250 g", "Cold store A", 88, 80, "warn", "Low soon"),
        ("BX-2222", "Dark chocolate 70%", "Dry store", 410, 150, "ok", "Healthy"),
        ("BX-2226", "Free-range eggs, 12", "Cold store B", 64, 100, "danger", "Reorder now"),
        ("BX-2230", "Granola, 500 g", "Dry store", 152, 90, "ok", "Healthy"),
    ]
    rows = ""
    for sku, name, place, on_hand, minimum, tone, state in stock:
        rows += (
            f'<tr><td class="mono">{sku}</td><td><b>{name}</b></td><td class="muted">{place}</td>'
            f'<td class="r"><input class="input num" style="width:92px;text-align:right" value="{on_hand}" aria-label="On hand for {name}"></td>'
            f'<td class="r"><input class="input num" style="width:92px;text-align:right" value="{minimum}" aria-label="Minimum for {name}"></td>'
            f'<td><span class="pill pill--{tone}">{state}</span></td></tr>'
        )
    css = ".grid-edit td:nth-child(n+4):nth-child(-n+5){padding-top:6px;padding-bottom:6px}.grid-edit tr:focus-within td{background:var(--soft)}.savebar{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-top:16px;padding:12px 16px;background:var(--color-ink);color:var(--color-neutral);border-radius:var(--radius)}"
    body = f"""
<div class="app">
{sidebar("Stockroom", "S", [("box", "Stock", ""), ("truck", "Deliveries", "3"), ("tag", "Products", ""), ("map", "Locations", ""), ("chart", "Reports", "")], "Stock", None, ("MS", "Marta Sosa", "Warehouse lead"))}
<main class="main">
  <div class="top"><div><h1>Stock count</h1><p class="sub">Tuesday count · Cold store and dry store · 6 of 214 products shown</p></div><div class="actions"><button class="btn">{icon("download")}Import counts</button><button class="btn btn--primary">{icon("check")}Submit count</button></div></div>
  <div class="actions" style="margin-bottom:14px"><div class="search" style="width:min(300px,70vw)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Scan or type a SKU" aria-label="Scan or type a SKU" autofocus></div><button class="btn">{icon("filter")}Location: all</button><span class="pill pill--danger">2 below minimum</span></div>
  <div class="table-wrap"><table class="grid-edit"><thead><tr><th>SKU</th><th>Product</th><th>Location</th><th class="r">Counted</th><th class="r">Minimum</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>
  <div class="savebar" role="status"><span><b>3 counts changed</b> since the last save</span><div class="actions"><button class="btn btn--sm btn--ghost" style="color:var(--color-neutral)">Discard</button><button class="btn btn--sm btn--primary" style="background:var(--color-neutral);color:var(--color-ink);border-color:var(--color-neutral)">Save changes</button></div></div>
</main></div>"""
    return Screen(
        "table-editable-grid", "Table: editable grid for fast entry", "A grid whose number cells are inputs: scan or type a SKU, tab through counts, low-stock status, and a sticky save bar that says how many cells changed.",
        "harbour", "inter", css + SPLIT, body, ["box", "truck", "tag", "map", "chart", "search", "filter", "download", "check"], ["practical", "fast", "light"], ["inventory", "warehouse", "data entry", "spreadsheet", "back office"], "dense",
        uses="repetitive data entry where speed matters: counts, timesheets, prices, scores; keyboard first, with a clear unsaved-changes bar",
        tags=["table", "editable", "data entry", "inputs", "sticky save bar"],
    )


ALL = [data_table, master_detail, kanban, editable_grid]
