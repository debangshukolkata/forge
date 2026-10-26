"""Ten back-office screens: approvals, audit log, order fulfilment, stock levels, receivables ageing, a support queue, a CSV import mapper,
a report builder, a jobs monitor and a resource timeline (D-487). They are the screens that office staff and operators live in all day, so
they are dense, keyboard friendly and show state in the form (pills, meters, timers) as well as in numbers."""

from __future__ import annotations

from .kit import bar_chart, icon, sidebar, spark
from .screen import Screen

SPLIT = "@media (max-width:1100px){.split{grid-template-columns:minmax(0,1fr)!important}}"
STAGES = ".stages{grid-template-columns:repeat(5,minmax(0,1fr))}@media (max-width:860px){.stages{grid-template-columns:repeat(2,minmax(0,1fr))}}"


def approval_queue() -> Screen:
    queue = [
        (
            "ER-2291",
            "Client dinner and travel",
            "Priya Nair",
            "Expense",
            "$1,284.00",
            "warn",
            "6 h left",
            True,
        ),
        (
            "PO-1190",
            "Laptop refresh, 12 units",
            "Marcus Webb",
            "Purchase",
            "$18,960.00",
            "danger",
            "Overdue 1 d",
            False,
        ),
        (
            "TO-0412",
            "8 days off, 14 to 23 May",
            "Sofia Lindqvist",
            "Leave",
            "8 days",
            "ok",
            "2 d left",
            False,
        ),
        ("ER-2288", "Conference ticket", "Tomas Beran", "Expense", "$640.00", "ok", "3 d left", False),
        ("VN-0077", "New vendor: Kestrel", "Ayesha Rahman", "Vendor", "n/a", "warn", "1 d left", False),
        (
            "PO-1187",
            "Office chairs, 30 units",
            "Marcus Webb",
            "Purchase",
            "$7,350.00",
            "danger",
            "Overdue 3 h",
            False,
        ),
    ]
    rows = ""
    for number, title, who, kind, amount, tone, due, selected in queue:
        mark = ' style="background:var(--soft)"' if selected else ""
        checked = " checked" if number in ("ER-2291", "ER-2288") else ""
        rows += (
            f'<tr{mark}><td style="width:44px"><input type="checkbox" aria-label="Select {number}"{checked}></td>'
            f'<td><div class="cell-main"><div><b>{title}</b><span class="mono">{number} · {who}</span></div></div></td>'
            f'<td><span class="pill">{kind}</span></td><td class="r num"><b>{amount}</b></td><td><span class="pill pill--{tone}">{due}</span></td></tr>'
        )
    body = f"""
<div class="app">
{sidebar("Signoff", "S", [("inbox", "Approvals", "14"), ("file", "My requests", ""), ("users", "Delegates", ""), ("shield", "Policies", ""), ("clock", "History", "")], "Approvals", None, ("DK", "Dana Kowalski", "Finance approver"))}
<main class="main">
  <div class="top"><div><h1>Approval queue</h1><p class="sub">14 waiting · 2 past their deadline · average decision time 5 h</p></div>
    <div class="seg" role="group" aria-label="Whose requests"><button aria-pressed="true">Assigned to me</button><button aria-pressed="false">My team</button><button aria-pressed="false">Everyone</button></div></div>
  <div class="grid cols-3" style="margin-bottom:16px">
    <div class="card kpi"><div class="label">Waiting for you</div><div class="value">14</div><span class="delta delta--down">{icon("up")}3 more than yesterday</span></div>
    <div class="card kpi"><div class="label">Oldest request</div><div class="value">2 d 4 h</div><span class="muted">PO-1190, Marcus Webb</span></div>
    <div class="card kpi"><div class="label">Decided this week</div><div class="value">61</div><span class="delta delta--up">{icon("up")}94% inside the deadline</span></div>
  </div>
  <div class="grid split" style="grid-template-columns:minmax(0,1fr) 350px;align-items:start">
    <section aria-label="Requests">
      <div class="actions" style="margin-bottom:12px"><div class="search" style="width:min(240px,100%)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search requests" aria-label="Search requests"></div><button class="btn">{icon("filter")}Type</button><button class="btn">{icon("clock")}Deadline</button></div>
      <div class="table-wrap"><table><thead><tr><th><span class="sr">Select</span></th><th>Request</th><th>Type</th><th class="r">Amount</th><th>Deadline</th></tr></thead><tbody>{rows}</tbody></table></div>
      <div class="actions" style="margin-top:12px;padding:10px 14px;border-radius:var(--r);background:var(--soft)" role="status"><b>2 selected</b><span class="muted">$1,924.00 in total</span><span style="flex:1"></span><button class="btn btn--sm btn--danger">Reject</button><button class="btn btn--sm btn--primary">{icon("check")}Approve both</button></div>
    </section>
    <section class="card" aria-labelledby="req">
      <div class="card-head" style="align-items:flex-start"><div><p class="mono muted">ER-2291 · submitted today, 08:41</p><h2 id="req" style="font-size:1.25rem;margin-top:4px">Client dinner and travel</h2></div><span class="pill pill--warn">6 h left</span></div>
      <div class="cell-main" style="margin-bottom:16px"><span class="avatar">PN</span><div><b>Priya Nair</b><span>Sales · reports to Marcus Webb</span></div></div>
      <h3 style="margin-bottom:6px">Policy checks</h3>
      <ul class="list" style="margin-bottom:14px"><li>{icon("check")}<span>Receipts attached for every line</span><span class="pill pill--ok" style="margin-left:auto">Pass</span></li><li>{icon("check")}<span>Within the monthly travel budget</span><span class="pill pill--ok" style="margin-left:auto">Pass</span></li><li>{icon("help")}<span>Dinner above the $90 a head limit</span><span class="pill pill--warn" style="margin-left:auto">Review</span></li></ul>
      <h3 style="margin-bottom:6px">What changed since the last version</h3>
      <div class="table-wrap" style="margin-bottom:14px"><table><thead><tr><th>Field</th><th>Before</th><th>Now</th></tr></thead><tbody>
        <tr><td>Dinner, 4 guests</td><td class="num muted"><s>$420.00</s></td><td class="num"><b>$384.00</b></td></tr>
        <tr><td>Train, Lisbon to Porto</td><td class="num muted">$96.00</td><td class="num">$96.00</td></tr>
        <tr><td>Hotel, 1 night</td><td class="num muted"><s>none</s></td><td class="num"><b>$164.00</b></td></tr></tbody></table></div>
      <div class="field" style="margin-bottom:14px"><label for="note">Note to Priya (optional)</label><textarea class="textarea" id="note" placeholder="Say why you are asking for changes or rejecting"></textarea></div>
      <div class="actions" style="justify-content:flex-end"><button class="btn btn--danger">Reject</button><button class="btn">Ask for changes</button><button class="btn btn--primary">{icon("check")}Approve $1,284.00</button></div>
    </section>
  </div>
</main></div>"""
    return Screen(
        "approval-queue",
        "Approvals: queue with decision panel",
        "A queue of requests with deadline pills, a bulk-decision bar and a decision panel: policy checks, what changed since the last version, a note and approve, ask or reject.",
        "slate",
        "inter",
        SPLIT,
        body,
        ["inbox", "file", "users", "shield", "clock", "search", "filter", "check", "up", "help"],
        ["businesslike", "precise", "light"],
        ["approvals", "approval", "approve", "expenses", "expense claims", "purchase orders", "purchasing", "finance", "workflow", "back office"],
        "balanced",
        uses="anyone who decides on other people's requests: expenses, purchase orders, leave, vendors, access; shows what is asked, what changed and what the policy says",
        tags=["queue", "approval", "decision panel", "deadline", "bulk actions", "diff", "side navigation"],
    )


def audit_log() -> Screen:
    events = [
        (
            "09:41:07",
            "AB",
            "Amara Brandt",
            "Admin",
            "permission",
            "Permission changed",
            "role/finance-viewer",
            "81.20.14.6",
            "Lisbon",
            True,
        ),
        (
            "09:38:52",
            "LF",
            "Luca Ferrante",
            "Editor",
            "ok",
            "Exported",
            "report/q1-revenue.csv",
            "81.20.14.9",
            "Lisbon",
            False,
        ),
        (
            "09:30:15",
            "SY",
            "svc-billing",
            "Service account",
            "info",
            "Updated",
            "invoice/48212",
            "10.4.2.18",
            "Internal",
            False,
        ),
        (
            "09:12:44",
            "HT",
            "Hana Takeda",
            "Editor",
            "danger",
            "Deleted",
            "customer/2291",
            "92.51.60.3",
            "Porto",
            False,
        ),
        (
            "08:55:03",
            "NH",
            "Noor Haddad",
            "Viewer",
            "ok",
            "Signed in",
            "session/9f31",
            "188.12.7.40",
            "Faro",
            False,
        ),
        (
            "08:41:30",
            "AB",
            "Amara Brandt",
            "Admin",
            "warn",
            "API key created",
            "key/ci-deploy",
            "81.20.14.6",
            "Lisbon",
            False,
        ),
    ]
    rows = ""
    for clock, initials, name, role, tone, action, target, ip, place, open_ in events:
        rows += (
            f'<tr><td class="mono muted" style="white-space:nowrap">{clock}</td>'
            f'<td><div class="cell-main"><span class="avatar">{initials}</span><div><b>{name}</b><span>{role}</span></div></div></td>'
            f'<td><span class="pill pill--{tone}">{action}</span></td><td><span class="mono">{target}</span><div class="muted" style="font-size:.85rem">{ip} · {place}</div></td>'
            f'<td class="r"><button class="btn btn--sm btn--icon btn--ghost" aria-label="{"Hide" if open_ else "Show"} details" aria-expanded="{"true" if open_ else "false"}">{icon("chevron")}</button></td></tr>'
        )
        if open_:
            rows += (
                '<tr><td colspan="5" style="background:var(--hover);padding:16px 20px"><div class="grid cols-2">'
                '<div><div class="label muted" style="margin-bottom:6px">Before</div><pre class="mono" style="margin:0;padding:12px;border-radius:var(--r);border:1px solid var(--color-border);background:var(--color-surface);font-size:.85rem;overflow:auto">role: "finance-viewer"\npermissions:\n  - reports.read\n  - invoices.read</pre></div>'
                '<div><div class="label muted" style="margin-bottom:6px">After</div><pre class="mono" style="margin:0;padding:12px;border-radius:var(--r);border:1px solid var(--color-border);background:var(--color-surface);font-size:.85rem;overflow:auto">role: "finance-viewer"\npermissions:\n  - reports.read\n  - invoices.read\n  - invoices.export</pre></div>'
                '</div><p class="muted" style="margin-top:10px;font-size:.85rem">Request 7c2e91f0 · entry 48,213 · hash 4be1…c90a, chain verified</p></td></tr>'
            )
    body = f"""
<div class="app">
{sidebar("Ledgerwatch", "L", [("home", "Overview", ""), ("shield", "Audit log", ""), ("users", "People", ""), ("key", "Access", ""), ("settings", "Settings", "")], "Audit log", None, ("AB", "Amara Brandt", "Security admin"))}
<main class="main">
  <div class="top"><div><h1>Audit log</h1><p class="sub">48,213 events in the last 30 days · every entry is signed and cannot be edited</p></div><div class="actions"><button class="btn">{icon("download")}Export CSV</button><button class="btn btn--primary">{icon("bell")}Create alert</button></div></div>
  <div class="actions" style="margin-bottom:14px"><div class="search" style="width:min(320px,100%)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search actor, resource or request id" aria-label="Search the log"></div>
    <select class="select" style="width:auto" aria-label="Actor"><option>Any actor</option><option>People</option><option>Service accounts</option></select><select class="select" style="width:auto" aria-label="Action"><option>Any action</option><option>Deleted</option><option>Permission changed</option><option>Exported</option></select>
    <div class="seg" role="group" aria-label="Period"><button aria-pressed="false">24 h</button><button aria-pressed="false">7 days</button><button aria-pressed="true">30 days</button></div></div>
  <div class="grid split" style="grid-template-columns:minmax(0,1fr) 250px;align-items:start">
    <div><div class="table-wrap"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource and origin</th><th><span class="sr">Details</span></th></tr></thead><tbody>{rows}</tbody></table></div>
      <div class="pager"><span>Showing 1 to 6 of 48,213</span><div class="actions"><button class="btn btn--sm" disabled>Previous</button><button class="btn btn--sm">Next</button></div></div></div>
    <aside class="grid" aria-label="Log health">
      <section class="card"><h2 style="margin-bottom:10px">Retention</h2><p class="muted" style="margin-bottom:10px">400 days kept, then archived to cold storage.</p><div class="meter" role="img" aria-label="31 percent of the retention period used"><i style="width:31%"></i></div><p class="muted" style="margin-top:8px;font-size:.85rem">Oldest entry: 124 days ago</p></section>
      <section class="card"><h2 style="margin-bottom:10px">Integrity</h2><ul class="list"><li>{icon("check")}<span>Hash chain verified</span></li><li>{icon("clock")}<span class="muted">Last check 09:00</span></li></ul></section>
      <section class="card"><h2 style="margin-bottom:10px">Most active</h2><ul class="list"><li><span class="avatar">AB</span><span>Amara Brandt</span><b class="num" style="margin-left:auto">412</b></li><li><span class="avatar">SY</span><span>svc-billing</span><b class="num" style="margin-left:auto">9,880</b></li></ul></section>
    </aside>
  </div>
</main></div>"""
    return Screen(
        "audit-log",
        "Audit log: events with before and after",
        "A filterable stream of who did what: actor, action pill, resource, origin, an expanded entry with a before and after comparison, and the retention and integrity of the log.",
        "mono",
        "inter",
        SPLIT,
        body,
        [
            "home",
            "shield",
            "users",
            "key",
            "settings",
            "search",
            "download",
            "bell",
            "check",
            "clock",
            "chevron",
        ],
        ["precise", "serious", "light"],
        ["audit", "security", "compliance", "admin", "activity log", "back office"],
        "dense",
        uses="proving who changed what and when: security, compliance, admin consoles, any product with roles and sensitive data",
        tags=["log", "audit", "filters", "diff", "expandable rows", "retention", "side navigation"],
    )


def order_fulfilment() -> Screen:
    stages = [
        ("New", "18", False),
        ("Picking", "11", True),
        ("Packed", "7", False),
        ("Shipped today", "42", False),
        ("Problems", "3", False),
    ]
    cards = "".join(
        f'<a href="#" class="card" style="padding:14px 16px;text-decoration:none;color:inherit;{"box-shadow:inset 0 -3px 0 var(--color-primary)" if sel else ""}"><div class="label muted">{name}</div><div class="num" style="font:600 1.6rem var(--font-display)">{n}</div></a>'
        for name, n, sel in stages
    )
    orders = [
        ("#31842", "Jonas Ek", "3 items", "Picking", "info", 2, True),
        ("#31841", "Mei Tanaka", "1 item", "Picking", "info", 2, False),
        ("#31840", "Rui Almeida", "5 items", "Packed", "ok", 3, False),
        ("#31839", "Clara Voss", "2 items", "Problem: address", "danger", 1, False),
        ("#31838", "Ola Nilsen", "4 items", "New", "", 1, False),
    ]
    rows = ""
    for number, who, items, stage, tone, step, selected in orders:
        dots = "".join(
            f'<i style="width:22px;height:6px;border-radius:999px;background:{"var(--color-primary)" if i < step else "var(--color-border)"}"></i>'
            for i in range(4)
        )
        rows += (
            f'<tr{" style=background:var(--soft)" if selected else ""}><td class="mono"><b>{number}</b></td><td>{who}<div class="muted" style="font-size:.85rem">{items}</div></td>'
            f'<td><span style="display:flex;gap:3px" aria-hidden="true">{dots}</span></td><td><span class="pill{" pill--" + tone if tone else ""}">{stage}</span></td></tr>'
        )
    body = f"""
<div class="app">
{sidebar("Dispatch", "D", [("box", "Fulfilment", "11"), ("truck", "Shipments", ""), ("tag", "Products", ""), ("map", "Warehouses", ""), ("chart", "Reports", "")], "Fulfilment", None, ("MS", "Marta Sosa", "Warehouse lead"))}
<main class="main">
  <div class="top"><div><h1>Order fulfilment</h1><p class="sub">Lisbon warehouse · cut-off for same-day dispatch is 15:30</p></div><div class="actions"><button class="btn">{icon("download")}Pick list</button><button class="btn btn--primary">{icon("send")}Print 7 labels</button></div></div>
  <div class="grid stages" style="margin-bottom:16px">{cards}</div>
  <div class="grid split" style="grid-template-columns:minmax(0,1fr) minmax(300px,380px);align-items:start">
    <div class="table-wrap"><table><thead><tr><th>Order</th><th>Customer</th><th>Progress</th><th>Stage</th></tr></thead><tbody>{rows}</tbody></table></div>
    <section class="card" aria-labelledby="ord">
      <div class="card-head"><div><p class="mono muted">Order #31842</p><h2 id="ord" style="font-size:1.2rem">Jonas Ek</h2></div><span class="pill pill--info">Picking</span></div>
      <ul class="list" style="margin-bottom:12px"><li><span class="avatar" style="border-radius:var(--r)">{icon("box")}</span><div><b>Trail jacket, green, M</b><div class="muted" style="font-size:.85rem">Aisle B4 · shelf 2</div></div><b class="num" style="margin-left:auto">x1</b></li>
        <li><span class="avatar" style="border-radius:var(--r)">{icon("box")}</span><div><b>Merino socks, 3 pack</b><div class="muted" style="font-size:.85rem">Aisle C1 · shelf 4</div></div><b class="num" style="margin-left:auto">x2</b></li></ul>
      <div class="grid cols-2" style="margin-bottom:14px"><div><div class="label muted">Ship to</div><p>Storgata 14<br>0184 Oslo, Norway</p></div><div><div class="label muted">Carrier</div><p>Nordic Post, tracked<br>Delivery 3 to 4 days</p></div></div>
      <div class="field" style="margin-bottom:14px"><label for="box">Box size</label><select class="select" id="box"><option>Small, 30 x 20 x 10 cm</option><option>Medium, 40 x 30 x 15 cm</option></select></div>
      <div class="actions" style="justify-content:flex-end"><button class="btn">Report a problem</button><button class="btn btn--primary">{icon("check")}Mark as packed</button></div>
    </section>
  </div>
</main></div>"""
    return Screen(
        "order-fulfilment",
        "Orders: fulfilment pipeline with order panel",
        "Stage counters across the top, an order list with a four-step progress bar and stage pill, and the selected order's pick list, address, carrier and box size with a mark-as-packed action.",
        "harbour",
        "manrope",
        SPLIT + STAGES,
        body,
        ["box", "truck", "tag", "map", "chart", "download", "send", "check"],
        ["practical", "fast", "light"],
        ["orders", "fulfilment", "warehouse", "shipping", "ecommerce", "back office"],
        "balanced",
        uses="the people who pick, pack and ship: warehouse, e-commerce back office, service dispatch; stage counters, one order at a time",
        tags=["orders", "pipeline", "progress", "pick list", "detail panel", "side navigation"],
    )


def inventory_levels() -> Screen:
    stock = [
        ("Oat flour, 25 kg", "FL-0021", 148, 120, "ok", "Healthy", 74),
        ("Sea salt, 10 kg", "SL-0007", 34, 40, "warn", "Low", 34),
        ("Rye starter, 5 kg", "ST-0003", 6, 20, "danger", "Below minimum", 12),
        ("Paper bags, large", "PK-0140", 1200, 800, "ok", "Healthy", 82),
        ("Butter, 10 kg block", "DA-0012", 0, 15, "danger", "Out of stock", 0),
    ]
    rows = ""
    for name, sku, on_hand, minimum, tone, state, fill in stock:
        rows += (
            f'<tr><td><b>{name}</b><div class="mono muted" style="font-size:.85rem">{sku}</div></td><td class="r num"><b>{on_hand:,}</b></td>'
            f'<td style="min-width:150px"><div class="meter" role="img" aria-label="{fill} percent of the target level"><i style="width:{fill}%;background:var(--color-{"ok" if tone == "ok" else tone})"></i></div><div class="muted num" style="font-size:.8rem;margin-top:4px">Minimum {minimum:,}</div></td>'
            f'<td><span class="pill pill--{tone}">{state}</span></td><td class="r"><button class="btn btn--sm">Reorder</button></td></tr>'
        )
    body = f"""
<div class="app">
{sidebar("Pantry", "P", [("box", "Stock levels", "3"), ("truck", "Deliveries", "2"), ("tag", "Products", ""), ("map", "Locations", ""), ("chart", "Waste", "")], "Stock levels", None, ("OL", "Olu Lawal", "Kitchen manager"))}
<main class="main">
  <div class="top"><div><h1>Stock levels</h1><p class="sub">Main kitchen · counted this morning at 06:40</p></div><div class="actions"><button class="btn">{icon("download")}Export</button><button class="btn btn--primary">{icon("plus")}Adjust stock</button></div></div>
  <div class="card" style="display:flex;gap:14px;align-items:center;margin-bottom:16px;background:color-mix(in srgb,var(--color-warn) 10%,var(--color-surface));border-color:color-mix(in srgb,var(--color-warn) 35%,var(--color-border))" role="status"><span class="pill pill--warn" style="flex:none">3 alerts</span><span>Three products are below their minimum. Reordering them costs about $2,140 and the supplier needs 2 days.</span></div>
  <div class="tabs" style="margin-bottom:14px" role="tablist"><a href="#" aria-current="page">Main kitchen</a><a href="#">Cold store</a><a href="#">Dry store</a><a href="#">Bakery counter</a></div>
  <div class="grid split" style="grid-template-columns:minmax(0,1fr) 320px;align-items:start">
    <div class="table-wrap"><table><thead><tr><th>Product</th><th class="r">On hand</th><th>Level</th><th>Status</th><th><span class="sr">Action</span></th></tr></thead><tbody>{rows}</tbody></table></div>
    <section class="card" aria-labelledby="sug"><div class="card-head"><h2 id="sug">Suggested order</h2><span class="pill pill--info">Greenfield Foods</span></div>
      <ul class="list" style="margin-bottom:12px"><li><span>Rye starter, 5 kg</span><b class="num" style="margin-left:auto">x 20</b></li><li><span>Butter, 10 kg block</span><b class="num" style="margin-left:auto">x 15</b></li><li><span>Sea salt, 10 kg</span><b class="num" style="margin-left:auto">x 10</b></li></ul>
      <div class="grid cols-2" style="margin-bottom:14px"><div><div class="label muted">Estimate</div><b class="num" style="font:600 1.3rem var(--font-display)">$2,140.00</b></div><div><div class="label muted">Arrives</div><b style="font:600 1.3rem var(--font-display)">Thursday</b></div></div>
      <button class="btn btn--primary" style="width:100%">{icon("send")}Create purchase order</button></section>
  </div>
</main></div>"""
    return Screen(
        "inventory-levels",
        "Stock levels: alerts, level bars and reorder",
        "Stock by location with a level bar against the minimum, status pills (healthy, low, below minimum, out), a warning banner and a suggested purchase order for the items to reorder.",
        "paper",
        "jakarta",
        SPLIT,
        body,
        ["box", "truck", "tag", "map", "chart", "download", "plus", "send"],
        ["practical", "calm", "light"],
        ["inventory", "stock", "kitchen", "retail", "purchasing", "back office"],
        "balanced",
        uses="knowing what is running out and ordering it: stock rooms, kitchens, shops, spare parts, supplies",
        tags=["stock", "levels", "alerts", "reorder", "meters", "tabs", "side navigation"],
    )


def invoice_ageing() -> Screen:
    buckets = ["Current", "1 to 30", "31 to 60", "61 to 90", "90+"]
    customers = [
        (
            "Alder &amp; Finch Packaging",
            "$24,300",
            "$11,200",
            "$9,800",
            "$0",
            "$0",
            "$45,300",
            "Reminder sent 2 d ago",
        ),
        ("Kestrel Components", "$8,100", "$0", "$0", "$14,950", "$6,400", "$29,450", "Called on 3 March"),
        ("Marlow Office Supply", "$3,915", "$2,400", "$0", "$0", "$0", "$6,315", "No contact needed"),
        (
            "Tern Logistics",
            "$0",
            "$7,200",
            "$7,200",
            "$7,200",
            "$0",
            "$21,600",
            "Promised payment on 21 March",
        ),
        ("Brightwell Studio", "$12,600", "$0", "$0", "$0", "$0", "$12,600", "No contact needed"),
    ]
    rows = ""
    for name, current, d30, d60, d90, d90plus, total, note in customers:
        rows += (
            f'<tr><td><b>{name}</b><div class="muted" style="font-size:.85rem">{note}</div></td><td class="r num">{current}</td><td class="r num">{d30}</td><td class="r num">{d60}</td>'
            f'<td class="r num">{d90}</td><td class="r num">{d90plus}</td><td class="r num"><b>{total}</b></td><td class="r"><button class="btn btn--sm">{icon("mail")}Remind</button></td></tr>'
        )
    chart = bar_chart(
        [48.9, 20.8, 17.0, 22.2, 6.4],
        buckets,
        height=170,
        highlight=3,
        title="Outstanding balance by age, in thousands of dollars",
    )
    body = f"""
<div class="app">
{sidebar("Ledgerline", "L", [("home", "Overview", ""), ("file", "Invoices", "9"), ("card", "Receivables", ""), ("users", "Customers", ""), ("chart", "Reports", "")], "Receivables", None, ("SL", "Soren Lindqvist", "Credit controller"))}
<main class="main">
  <div class="top"><div><h1>Receivables ageing</h1><p class="sub">As of 14 March · 42 open invoices across 18 customers</p></div><div class="actions"><button class="btn">{icon("download")}Statement run</button><button class="btn btn--primary">{icon("send")}Send 6 reminders</button></div></div>
  <div class="grid cols-4" style="margin-bottom:16px">
    <div class="card kpi"><div class="label">Outstanding</div><div class="value">$115,265</div><span class="muted">42 invoices</span></div>
    <div class="card kpi"><div class="label">Overdue</div><div class="value">$66,350</div><span class="delta delta--down">{icon("up")}$4,100 since last week</span></div>
    <div class="card kpi"><div class="label">Average days to pay</div><div class="value">34</div><span class="delta delta--up">{icon("down")}2 days faster</span></div>
    <div class="card kpi"><div class="label">Collected this month</div><div class="value">$87,420</div><span class="muted">74% of target</span></div>
  </div>
  <div class="grid split" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);margin-bottom:16px">
    <section class="card" aria-labelledby="age"><div class="card-head"><div><h2 id="age">Balance by age</h2><p>In thousands of dollars</p></div></div>{chart}</section>
    <section class="card" aria-labelledby="seq"><div class="card-head"><h2 id="seq">Reminder sequence</h2><button class="btn btn--sm">Edit</button></div>
      <ul class="list"><li><span class="pill pill--info">Day 1</span><span>Friendly reminder by email</span></li><li><span class="pill pill--warn">Day 14</span><span>Second notice with statement</span></li><li><span class="pill pill--danger">Day 30</span><span>Call from the credit controller</span></li></ul></section>
  </div>
  <div class="table-wrap"><table><thead><tr><th>Customer</th><th class="r">Current</th><th class="r">1 to 30</th><th class="r">31 to 60</th><th class="r">61 to 90</th><th class="r">90+</th><th class="r">Total</th><th><span class="sr">Action</span></th></tr></thead><tbody>{rows}</tbody></table></div>
</main></div>"""
    return Screen(
        "invoice-ageing",
        "Receivables: ageing buckets and reminders",
        "Outstanding and overdue totals, a bar chart of balances by age with the 61 to 90 bucket highlighted, the reminder sequence and a customer table with a balance per bucket and a remind action.",
        "slate",
        "inter",
        SPLIT,
        body,
        ["home", "file", "card", "users", "chart", "download", "send", "mail", "up", "down"],
        ["businesslike", "precise", "light"],
        ["accounting", "receivables", "invoices", "credit control", "finance", "back office"],
        "dense",
        uses="chasing money that is owed: finance and credit control, subscriptions, B2B billing; see which age bucket hurts and who to remind",
        tags=["finance", "ageing", "bar chart", "table", "reminders", "kpi", "side navigation"],
    )


def helpdesk_queue() -> Screen:
    tickets = [
        (
            "T-7421",
            "Refund not received after 10 days",
            "Priya Nair",
            "Urgent",
            "danger",
            "38 min left",
            "danger",
            "JB",
            "Email",
        ),
        (
            "T-7418",
            "Cannot log in after changing phone",
            "Elias Moreau",
            "High",
            "warn",
            "2 h 10 min left",
            "warn",
            "AM",
            "Chat",
        ),
        (
            "T-7415",
            "Invoice shows the wrong VAT number",
            "Studio Marlowe",
            "Normal",
            "info",
            "6 h left",
            "ok",
            "JB",
            "Email",
        ),
        ("T-7411", "How do I export my data?", "Kenji Mori", "Low", "", "1 d left", "ok", "TW", "Web form"),
        (
            "T-7409",
            "Parcel delivered to a neighbour",
            "Ola Nilsen",
            "High",
            "warn",
            "Breached 12 min ago",
            "danger",
            "None",
            "Phone",
        ),
    ]
    rows = ""
    for number, subject, who, prio, tone, sla, sla_tone, agent, channel in tickets:
        assignee = (
            f'<span class="avatar">{agent}</span>'
            if agent != "None"
            else '<span class="pill">Unassigned</span>'
        )
        rows += (
            f'<tr><td><b>{subject}</b><div class="muted" style="font-size:.85rem"><span class="mono">{number}</span> · {who} · {channel}</div></td>'
            f'<td><span class="pill{" pill--" + tone if tone else ""}">{prio}</span></td><td><span class="pill pill--{sla_tone}">{sla}</span></td><td>{assignee}</td></tr>'
        )
    agents = [("Jess Boateng", "9 open", 82), ("Alvaro Mena", "6 open", 55), ("Tilda Wren", "4 open", 36)]
    load = "".join(
        f'<li style="flex-wrap:wrap"><span>{n}</span><span class="muted" style="margin-left:auto">{o}</span><div class="meter" style="flex-basis:100%" role="img" aria-label="{n}: {w} percent of capacity"><i style="width:{w}%"></i></div></li>'
        for n, o, w in agents
    )
    body = f"""
<div class="app">
{sidebar("Helpline", "H", [("inbox", "Queue", "42"), ("users", "Customers", ""), ("chat", "Macros", ""), ("chart", "Reports", ""), ("settings", "Settings", "")], "Queue", None, ("JB", "Jess Boateng", "Support agent"))}
<main class="main">
  <div class="top"><div><h1>Support queue</h1><p class="sub">42 open · 6 unassigned · first response time today 18 min</p></div><div class="actions"><button class="btn">{icon("filter")}Saved views</button><button class="btn btn--primary">{icon("plus")}New ticket</button></div></div>
  <div class="tabs" style="margin-bottom:14px" role="tablist"><a href="#" aria-current="page">Open <span class="pill" style="margin-left:6px">42</span></a><a href="#">Mine <span class="pill" style="margin-left:6px">9</span></a><a href="#">Unassigned <span class="pill pill--warn" style="margin-left:6px">6</span></a><a href="#">Escalated <span class="pill pill--danger" style="margin-left:6px">3</span></a><a href="#">Solved</a></div>
  <div class="grid split" style="grid-template-columns:minmax(0,1fr) 300px;align-items:start">
    <div><div class="actions" style="margin-bottom:12px"><div class="search" style="width:min(320px,100%)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search subject, customer or number" aria-label="Search tickets"></div><select class="select" style="width:auto" aria-label="Sort"><option>Sort: soonest deadline</option><option>Sort: newest</option><option>Sort: priority</option></select></div>
      <div class="table-wrap"><table><thead><tr><th>Ticket</th><th>Priority</th><th>Reply by</th><th>Agent</th></tr></thead><tbody>{rows}</tbody></table></div></div>
    <aside class="grid" aria-label="Team">
      <section class="card"><h2 style="margin-bottom:10px">Team workload</h2><ul class="list">{load}</ul></section>
      <section class="card"><h2 style="margin-bottom:10px">Quick replies</h2><ul class="list"><li><span>Refund status</span><button class="btn btn--sm" style="margin-left:auto">Use</button></li><li><span>Reset your password</span><button class="btn btn--sm" style="margin-left:auto">Use</button></li><li><span>Where is my parcel</span><button class="btn btn--sm" style="margin-left:auto">Use</button></li></ul></section>
    </aside>
  </div>
</main></div>"""
    return Screen(
        "helpdesk-queue",
        "Support queue: tickets with reply deadlines",
        "A ticket queue sorted by what is due: priority and reply-by pills that turn red as the deadline nears, assignee avatars, status tabs with counts, team workload meters and quick replies.",
        "harbour",
        "manrope",
        SPLIT,
        body,
        ["inbox", "users", "chat", "chart", "settings", "filter", "plus", "search"],
        ["practical", "calm", "light"],
        ["support", "tickets", "helpdesk", "customer service", "sla", "back office"],
        "dense",
        uses="working through a queue against a clock: support desks, IT service desks, claims, requests with service levels",
        tags=["queue", "tickets", "deadline", "workload", "tabs", "quick replies", "side navigation"],
    )


def csv_import() -> Screen:
    mapping = [
        ("Full Name", "Amara Okafor, Luca Ferrante", "Name", "ok", "Matched"),
        ("E-mail", "amara@brightwell.io", "Email", "ok", "Matched"),
        ("Tel", "+351 912 345 678", "Phone", "ok", "Matched"),
        ("Dept", "Design, Engineering", "Team", "warn", "Check"),
        ("Joined", "03/12/2024, 17/01/2025", "Start date", "warn", "Date format?"),
        ("Notes", "Prefers mornings", "Skip", "", "Skipped"),
    ]
    fields = ["Name", "Email", "Phone", "Team", "Start date", "Skip"]
    rows = ""
    for source, sample, target, tone, state in mapping:
        options = "".join(f"<option{' selected' if f == target else ''}>{f}</option>" for f in fields)
        rows += (
            f'<tr><td><b class="mono">{source}</b></td><td class="muted">{sample}</td><td style="width:210px"><select class="select" aria-label="Field for {source}">{options}</select></td>'
            f'<td><span class="pill{" pill--" + tone if tone else ""}">{state}</span></td></tr>'
        )
    steps = [("Upload", "done"), ("Map columns", "now"), ("Review", ""), ("Import", "")]
    stepper = "".join(
        f'<li style="flex:1;display:flex;align-items:center;gap:10px;{"" if s != "" else "color:var(--color-muted)"}"><span class="avatar" style="{"background:var(--color-primary);color:var(--color-on-primary)" if s else ""}">{icon("check") if s == "done" else i + 1}</span><b>{n}</b></li>'
        for i, (n, s) in enumerate(steps)
    )
    body = f"""
<div class="app">
{sidebar("Rosterly", "R", [("users", "People", ""), ("download", "Import", ""), ("calendar", "Schedules", ""), ("chart", "Reports", ""), ("settings", "Settings", "")], "Import", None, ("NH", "Noor Haddad", "HR coordinator"))}
<main class="main">
  <div class="top"><div><h1>Import people</h1><p class="sub">team-roster-march.csv · 1,204 rows · 6 columns found</p></div><div class="actions"><button class="btn">Replace file</button></div></div>
  <ol class="card" style="display:flex;gap:12px;list-style:none;margin:0 0 16px;padding:14px 20px;flex-wrap:wrap" aria-label="Steps">{stepper}</ol>
  <div class="grid split" style="grid-template-columns:minmax(0,1.6fr) minmax(280px,1fr);align-items:start">
    <section aria-labelledby="map"><h2 id="map" style="margin-bottom:10px">Match each column to a field</h2>
      <div class="table-wrap"><table><thead><tr><th>Your column</th><th>Sample values</th><th>Goes into</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></section>
    <section class="card" aria-labelledby="chk"><div class="card-head"><h2 id="chk">Checks on 1,204 rows</h2></div>
      <div class="meter" role="img" aria-label="97 percent of rows are valid" style="margin-bottom:12px"><i style="width:97%;background:var(--color-ok)"></i></div>
      <ul class="list" style="margin-bottom:12px"><li><span class="pill pill--ok">1,168</span><span>rows are ready</span></li><li><span class="pill pill--warn">29</span><span>rows need a look: unusual date format</span></li><li><span class="pill pill--danger">7</span><span>rows will be skipped: invalid email</span></li></ul>
      <div class="field is-error" style="margin-bottom:12px"><span class="label">First problems</span><div class="error">{icon("x")}Row 88: "amara@brightwell" is not an email address</div><div class="error">{icon("x")}Row 412: email is empty</div></div>
      <button class="btn" style="width:100%">{icon("download")}Download the error report</button></section>
  </div>
  <div class="actions" style="margin-top:16px;justify-content:space-between;padding:12px 16px;border-radius:var(--r);background:var(--color-surface);border:1px solid var(--color-border)"><button class="btn">Back</button><div class="actions"><span class="muted">Existing people with the same email are updated</span><button class="btn btn--primary">Import 1,168 rows</button></div></div>
</main></div>"""
    return Screen(
        "csv-import",
        "Import: map columns and check rows",
        "A four-step import: file summary, a column-to-field mapping table with sample values and match status, a validation summary with the first errors, and a footer that says exactly what will be imported.",
        "paper",
        "manrope",
        SPLIT,
        body,
        ["users", "download", "calendar", "chart", "settings", "check", "x"],
        ["practical", "careful", "light"],
        ["import", "csv", "data migration", "onboarding", "hr", "back office"],
        "balanced",
        uses="bringing a spreadsheet into the product: user lists, products, contacts, transactions; map, validate, then commit",
        tags=["import", "csv", "mapping", "validation", "stepper", "errors", "side navigation"],
    )


def report_builder() -> Screen:
    regions = [("North", True), ("South", True), ("East", False), ("West", True)]
    checks = "".join(
        f'<label class="check"><input type="checkbox"{" checked" if on else ""}>{name}</label>'
        for name, on in regions
    )
    data = [
        ("Lisbon", "$182,400", "1,204", "$151.50", "+12.4%"),
        ("Porto", "$131,950", "902", "$146.30", "+7.1%"),
        ("Braga", "$64,300", "455", "$141.30", "-2.8%"),
        ("Faro", "$48,120", "361", "$133.30", "+18.9%"),
    ]
    rows = "".join(
        f'<tr><td><b>{c}</b></td><td class="r num">{r}</td><td class="r num">{o}</td><td class="r num">{a}</td><td class="r num"><span class="delta delta--{"down" if d.startswith("-") else "up"}">{d}</span></td></tr>'
        for c, r, o, a, d in data
    )
    chart = bar_chart(
        [182, 132, 64, 48],
        ["Lisbon", "Porto", "Braga", "Faro"],
        height=150,
        highlight=0,
        title="Revenue by city, in thousands of dollars",
    )
    body = f"""
<div class="app">
{sidebar("Metrics", "M", [("chart", "Reports", ""), ("star", "Saved views", "8"), ("calendar", "Schedules", "3"), ("link", "Data sources", ""), ("settings", "Settings", "")], "Reports", None, ("LF", "Luca Ferrante", "Analyst"))}
<main class="main">
  <div class="top"><div><h1 class="sr">Revenue by city, Q1</h1><label class="sr" for="rn">Report name</label><input class="input" id="rn" value="Revenue by city, Q1" style="font:600 1.6rem var(--font-display);min-height:48px;max-width:min(520px,90vw)"><p class="sub" style="margin-top:6px">Edited by you 4 minutes ago · 1,204 orders in range</p></div>
    <div class="actions"><button class="btn">{icon("calendar")}Schedule</button><button class="btn">{icon("download")}Export</button><button class="btn btn--primary">{icon("check")}Save view</button></div></div>
  <div class="grid split" style="grid-template-columns:260px minmax(0,1fr);align-items:start">
    <aside class="card" aria-label="Filters"><h2 style="margin-bottom:12px">Filters</h2>
      <div class="field" style="margin-bottom:14px"><label for="dr">Date range</label><select class="select" id="dr"><option>Jan 1 to Mar 31, 2025</option><option>Last 30 days</option><option>Last quarter</option></select></div>
      <div class="field" style="margin-bottom:14px"><span class="label">Region</span><div style="display:grid;gap:8px">{checks}</div></div>
      <div class="field" style="margin-bottom:14px"><label for="cat">Product category</label><select class="select" id="cat"><option>All categories</option><option>Outdoor</option><option>Kitchen</option></select></div>
      <div class="field" style="margin-bottom:14px"><span class="label">Group by</span><div class="seg" role="group" aria-label="Group by"><button aria-pressed="true">City</button><button aria-pressed="false">Month</button><button aria-pressed="false">Product</button></div></div>
      <button class="btn" style="width:100%">Reset filters</button></aside>
    <div class="grid">
      <section class="card" aria-labelledby="cv"><div class="card-head"><div><h2 id="cv">Revenue by city</h2><p>Q1 2025 · 3 of 4 regions</p></div><div class="seg" role="group" aria-label="Metric"><button aria-pressed="true">Revenue</button><button aria-pressed="false">Orders</button></div></div>{chart}</section>
      <div class="table-wrap"><table><thead><tr><th>City</th><th class="r">Revenue</th><th class="r">Orders</th><th class="r">Average order</th><th class="r">Change</th></tr></thead><tbody>{rows}</tbody></table></div>
      <section class="card" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><span class="avatar">{icon("calendar")}</span><div><b>Sent every Monday at 08:00</b><div class="muted">To finance@brightwell.io and 2 others as a PDF</div></div><button class="btn btn--sm" style="margin-left:auto">Change schedule</button></section>
    </div>
  </div>
</main></div>"""
    return Screen(
        "report-builder",
        "Report builder: filters, preview and schedule",
        "An editable report name, a filter panel (date range, regions, category, group by), a live chart and table preview, and the schedule that sends it by email.",
        "ink",
        "inter",
        SPLIT,
        body,
        ["chart", "star", "calendar", "link", "settings", "download", "check"],
        ["precise", "focused", "dark"],
        ["reports", "analytics", "bi", "finance", "export", "scheduled reports", "back office"],
        "dense",
        uses="asking a question of the data and sending the answer on a schedule: reporting tools, finance, sales ops, admin consoles",
        tags=["report", "filters", "preview", "chart", "table", "schedule", "export", "side navigation"],
    )


def jobs_monitor() -> Screen:
    queues = [
        ("Email", "Healthy", "ok", [12, 14, 13, 18, 16, 20, 19, 22], "1,204 / h"),
        ("Exports", "Healthy", "ok", [4, 5, 5, 4, 6, 5, 6, 5], "86 / h"),
        ("Webhooks", "Degraded", "warn", [30, 28, 31, 24, 19, 15, 12, 9], "311 / h"),
        ("Imports", "Failing", "danger", [3, 3, 4, 2, 2, 1, 0, 0], "0 / h"),
    ]
    cards = "".join(
        f'<div class="card"><div class="label muted">{name}</div><div style="display:flex;justify-content:space-between;align-items:end;gap:8px;margin:8px 0"><span class="pill pill--{tone}">{state}</span>{spark(values, f"var(--color-{tone})" if tone != "ok" else "var(--color-primary)")}</div><div class="muted num">{rate}</div></div>'
        for name, state, tone, values, rate in queues
    )
    runs = [
        ("import-customers", "Imports", "09:41:02", "2m 14s", "3 of 3", "danger", "Failed", True),
        ("send-invoice-48212", "Email", "09:40:31", "1.2 s", "1 of 3", "ok", "Done", False),
        ("webhook-orders-created", "Webhooks", "09:40:12", "30 s", "2 of 5", "warn", "Retrying", False),
        ("export-q1-revenue", "Exports", "09:38:50", "14 s", "1 of 3", "ok", "Done", False),
        ("send-reminder-batch", "Email", "09:36:08", "6.4 s", "1 of 3", "ok", "Done", False),
    ]
    rows = "".join(
        f'<tr{" style=background:var(--soft)" if sel else ""}><td style="white-space:nowrap"><b class="mono">{name}</b><div class="muted" style="font-size:.85rem">{queue} queue</div></td><td class="mono muted">{start}</td><td class="r num">{dur}</td><td class="r num">{tries}</td><td><span class="pill pill--{tone}">{state}</span></td></tr>'
        for name, queue, start, dur, tries, tone, state, sel in runs
    )
    body = f"""
<div class="app">
{sidebar("Pipeline", "P", [("grid", "Overview", ""), ("layers", "Queues", "4"), ("clock", "Scheduled", ""), ("link", "Integrations", "1"), ("bell", "Alerts", "2")], "Queues", None, ("RK", "Ravi Kulkarni", "Platform engineer"))}
<main class="main">
  <div class="top"><div><h1>Background jobs</h1><p class="sub">Production · refreshed 5 seconds ago · 1 queue failing</p></div><div class="actions"><div class="seg" role="group" aria-label="Refresh"><button aria-pressed="true">Live</button><button aria-pressed="false">Paused</button></div><button class="btn">{icon("filter")}Failed only</button></div></div>
  <div class="grid cols-4" style="margin-bottom:16px">{cards}</div>
  <div class="grid split" style="grid-template-columns:minmax(0,1fr) 340px;align-items:start">
    <div class="table-wrap"><table><thead><tr><th>Job</th><th>Started</th><th class="r">Took</th><th class="r">Attempt</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>
    <section class="card" aria-labelledby="fail"><div class="card-head"><div><p class="mono muted">import-customers · run 91c4</p><h2 id="fail" style="font-size:1.2rem;margin-top:4px">Failed after 3 attempts</h2></div><span class="pill pill--danger">Failed</span></div>
      <p style="margin-bottom:10px">The import stopped at row 4,118 because the database refused a duplicate key.</p>
      <pre class="mono" style="margin:0 0 14px;padding:12px;border-radius:var(--r);border:1px solid var(--color-border);background:var(--color-neutral);font-size:.85rem;overflow:auto;white-space:pre-wrap">IntegrityError: duplicate key value violates
unique constraint "customers_email_key"
Key (email)=(amara@brightwell.io) already exists.</pre>
      <ul class="list" style="margin-bottom:14px"><li><span class="muted">Attempts</span><b class="num" style="margin-left:auto">3 of 3</b></li><li><span class="muted">Next retry</span><b style="margin-left:auto">None, retries used up</b></li><li><span class="muted">Triggered by</span><b style="margin-left:auto">Nightly schedule</b></li></ul>
      <div class="actions" style="justify-content:flex-end"><button class="btn btn--danger">Discard</button><button class="btn btn--primary">{icon("send")}Retry now</button></div></section>
  </div>
</main></div>"""
    return Screen(
        "jobs-monitor",
        "Jobs monitor: queues and a failed run",
        "Queue health cards with a throughput sparkline, a table of recent job runs (duration, attempt, status) and the detail of a failed run with its error text, attempts and retry or discard.",
        "ink",
        "jakarta",
        SPLIT,
        body,
        ["grid", "layers", "clock", "link", "bell", "filter", "send"],
        ["technical", "calm", "dark"],
        ["operations", "jobs", "queues", "devops", "monitoring", "integrations", "back office"],
        "dense",
        uses="watching work that runs in the background: queues, imports, exports, webhooks, scheduled tasks; spot the one that is failing and act on it",
        tags=[
            "monitoring",
            "queues",
            "jobs",
            "sparkline",
            "error detail",
            "retry",
            "dark",
            "side navigation",
        ],
    )


def resource_timeline() -> Screen:
    hours = ["08", "09", "10", "11", "12", "13", "14", "15", "16", "17"]
    head = "".join(
        f'<div class="muted num" style="font-size:.8rem;padding:8px 0 8px 6px;border-left:1px solid var(--color-border)">{h}:00</div>'
        for h in hours
    )
    resources = [
        (
            "Studio A",
            "Room, 12 people",
            [(1, 3, "Pilates, Group 1", "info"), (5, 2, "Workshop", "ok"), (8, 2, "Private lesson", "info")],
        ),
        (
            "Studio B",
            "Room, 6 people",
            [(2, 2, "Yoga basics", "ok"), (4, 3, "Team offsite", "warn"), (4, 2, "Yoga, Group 4", "danger")],
        ),
        (
            "Dr. Silva",
            "Physio",
            [(0, 2, "Assessment: Ek", "info"), (3, 1, "Follow-up: Tanaka", "ok"), (6, 3, "Clinic hours", "")],
        ),
        ("Van 1", "Equipment", [(1, 4, "Delivery run, north", "ok"), (7, 3, "Service", "warn")]),
        ("Van 2", "Equipment", [(2, 5, "Event set-up", "info")]),
    ]
    tone_css = {
        "info": "background:var(--soft);border-left:3px solid var(--color-primary)",
        "ok": "background:color-mix(in srgb,var(--color-ok) 14%,var(--color-surface));border-left:3px solid var(--color-ok)",
        "warn": "background:color-mix(in srgb,var(--color-warn) 15%,var(--color-surface));border-left:3px solid var(--color-warn)",
        "danger": "background:color-mix(in srgb,var(--color-danger) 13%,var(--color-surface));border-left:3px solid var(--color-danger)",
        "": "background:var(--hover);border-left:3px solid var(--color-border)",
    }
    lanes = ""
    for name, kind, items in resources:
        blocks = ""
        stacked = {}
        for start, span, label, tone in items:
            lane = stacked.get(start, 0)
            stacked[start] = lane + 1
            blocks += f'<div style="grid-column:{start + 1} / span {span};grid-row:{lane + 1};{tone_css[tone]};border-radius:6px;padding:4px 8px;font-size:.85rem;font-weight:600;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;min-width:0;margin-right:4px" title="{label}">{label}</div>'
        lanes += (
            f'<div style="display:grid;grid-template-columns:150px minmax(0,1fr);border-top:1px solid var(--color-border)"><div style="padding:12px 14px"><b>{name}</b><div class="muted" style="font-size:.85rem">{kind}</div></div>'
            f'<div style="display:grid;grid-template-columns:repeat(10,minmax(0,1fr));grid-auto-rows:34px;gap:4px 0;padding:10px 0;background:repeating-linear-gradient(90deg,transparent 0,transparent calc(10% - 1px),var(--color-border) calc(10% - 1px),var(--color-border) 10%)">{blocks}</div></div>'
        )
    body = f"""
<div class="app">
{sidebar("Bookable", "B", [("calendar", "Timeline", ""), ("users", "Resources", ""), ("inbox", "Requests", "3"), ("clock", "Availability", ""), ("settings", "Settings", "")], "Timeline", None, ("IM", "Ines Moreira", "Studio manager"))}
<main class="main">
  <div class="top"><div><h1>Thursday 20 March</h1><p class="sub">5 resources · 12 bookings · 1 conflict to resolve</p></div><div class="actions"><div class="seg" role="group" aria-label="View"><button aria-pressed="true">Day</button><button aria-pressed="false">Week</button></div><button class="btn btn--icon" aria-label="Previous day">{icon("chevron")}</button><button class="btn btn--icon" aria-label="Next day">{icon("chevron")}</button><button class="btn btn--primary">{icon("plus")}New booking</button></div></div>
  <div class="grid">
    <div class="table-wrap" style="padding:0"><div style="min-width:760px"><div style="display:grid;grid-template-columns:150px minmax(0,1fr)"><div class="muted" style="padding:8px 14px;font-size:.8rem">Resource</div><div style="display:grid;grid-template-columns:repeat(10,minmax(0,1fr))">{head}</div></div>{lanes}</div></div>
    <aside class="grid cols-2" aria-label="To place">
      <section class="card" style="border-color:color-mix(in srgb,var(--color-danger) 40%,var(--color-border))"><div class="card-head"><h2>Conflict</h2><span class="pill pill--danger">1</span></div><p style="margin-bottom:10px"><b>Team offsite</b> and <b>Yoga, Group 4</b> both want Studio B between 12:00 and 14:00.</p><div class="actions"><button class="btn btn--sm">Move offsite</button><button class="btn btn--sm btn--primary">Use Studio A</button></div></section>
      <section class="card"><div class="card-head"><h2>Waiting for a slot</h2></div><ul class="list"><li><div><b>Private lesson: Voss</b><div class="muted" style="font-size:.85rem">1 h · any room</div></div><button class="btn btn--sm" style="margin-left:auto">Place</button></li><li><div><b>Delivery: Marlow</b><div class="muted" style="font-size:.85rem">2 h · a van</div></div><button class="btn btn--sm" style="margin-left:auto">Place</button></li></ul></section>
    </aside>
  </div>
</main></div>"""
    return Screen(
        "resource-timeline",
        "Scheduling: resource timeline with conflicts",
        "A day timeline with one row per resource (rooms, staff, vehicles), booking blocks coloured by state, a clear conflict card with two ways out and a list of requests waiting for a slot.",
        "slate",
        "grotesk",
        SPLIT,
        body,
        ["calendar", "users", "inbox", "clock", "settings", "plus", "chevron"],
        ["businesslike", "clear", "light"],
        ["scheduling", "bookings", "rooms", "staff rota", "fleet", "resource planning", "back office"],
        "dense",
        uses="deciding who or what is where and when: rooms, clinics, vehicles, staff rotas; see gaps and conflicts across resources at a glance",
        tags=["timeline", "scheduling", "resources", "conflicts", "bookings", "side navigation"],
    )


ALL = [
    approval_queue,
    audit_log,
    order_fulfilment,
    inventory_levels,
    invoice_ageing,
    helpdesk_queue,
    csv_import,
    report_builder,
    jobs_monitor,
    resource_timeline,
]
