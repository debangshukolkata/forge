"""Four dashboards with different jobs and looks: sales KPIs, logistics operations, product analytics (dark) and a personal overview (D-366)."""

from __future__ import annotations

from .kit import bar_chart, donut, icon, line_chart, sidebar, spark
from .screen import Screen


def _kpi(label: str, value: str, delta: str, up: bool, note: str = "vs last month") -> str:
    arrow = icon("up" if up else "down")
    return (
        f'<article class="card kpi"><div class="label">{label}</div><div class="value">{value}</div>'
        f'<span class="delta delta--{"up" if up else "down"}">{arrow}{delta}</span> <span class="muted" style="font-size:.85rem">{note}</span></article>'
    )


def sales_kpi() -> Screen:
    orders = [
        ("#48213", "Hollis &amp; Park", "Mar 14", "$4,820.00", "ok", "Paid"),
        ("#48212", "Northwind Cycles", "Mar 14", "$1,240.50", "warn", "Pending"),
        ("#48211", "Lumen Studio", "Mar 13", "$9,115.00", "ok", "Paid"),
        ("#48210", "Fieldnote Press", "Mar 13", "$640.00", "danger", "Refunded"),
        ("#48209", "Orchard &amp; Vine", "Mar 12", "$2,380.75", "ok", "Paid"),
    ]
    rows = "".join(
        f'<tr><td class="mono">{n}</td><td><div class="cell-main"><span class="avatar">{c[0]}</span><b>{c}</b></div></td><td class="muted">{d}</td><td class="r num">{a}</td><td><span class="pill pill--{t}">{s}</span></td></tr>'
        for n, c, d, a, t, s in orders
    )
    chart = line_chart(
        [([42, 46, 44, 51, 58, 55, 63, 70, 66, 74, 81, 88], "var(--color-primary)"), ([30, 31, 33, 32, 36, 38, 37, 41, 43, 42, 46, 49], "var(--color-accent2)")],
        ["$100k", "$75k", "$50k", "$25k", "$0"],
        ["Apr", "Jun", "Aug", "Oct", "Dec", "Feb"],
        label="Revenue by month, this year and last year",
    )
    body = f"""
<div class="app">
{sidebar("Ledgerline", "L", [("home", "Overview", ""), ("chart", "Reports", ""), ("card", "Payments", "12"), ("users", "Customers", ""), ("box", "Products", "")], "Overview", [("Workspace", [("settings", "Settings", ""), ("help", "Help centre", "")])], ("JR", "Jordan Reyes", "Finance admin"))}
<main class="main">
  <div class="top"><div><h1>Revenue overview</h1><p class="sub">Last 12 months · all channels · updated 9 minutes ago</p></div>
    <div class="actions"><div class="seg" role="group" aria-label="Range"><button aria-pressed="false">30 days</button><button aria-pressed="false">90 days</button><button aria-pressed="true">12 months</button></div><button class="btn btn--primary">{icon("download")}Export report</button></div></div>
  <div class="grid cols-4">{_kpi("Revenue", "$418,230", "12.4%", True)}{_kpi("Orders", "3,284", "5.1%", True)}{_kpi("Average order", "$127.35", "2.3%", False)}{_kpi("Refund rate", "1.8%", "0.4 pts", True)}</div>
  <div class="grid" style="grid-template-columns:minmax(0,2fr) minmax(0,1fr);margin-top:16px" id="split">
    <section class="card" aria-labelledby="rev"><div class="card-head"><div><h2 id="rev">Revenue by month</h2><p>This year against last year</p></div>
      <div class="legend"><span><i style="background:var(--color-primary)"></i>This year</span><span><i style="background:var(--color-accent2)"></i>Last year</span></div></div>{chart}</section>
    <section class="card" aria-labelledby="chan"><div class="card-head"><h2 id="chan">Sales by channel</h2></div>
      <div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap">{donut([(52, "var(--color-primary)"), (31, "var(--color-accent2)"), (17, "color-mix(in srgb,var(--color-ink) 30%,var(--color-surface))")], centre="$418k", sub="12 months")}
      <ul class="list" style="flex:1;min-width:150px"><li><span class="legend"><i style="background:var(--color-primary)"></i></span>Online store<b class="num" style="margin-left:auto">52%</b></li><li><span class="legend"><i style="background:var(--color-accent2)"></i></span>Wholesale<b class="num" style="margin-left:auto">31%</b></li><li><span class="legend"><i style="background:color-mix(in srgb,var(--color-ink) 30%,var(--color-surface))"></i></span>Marketplaces<b class="num" style="margin-left:auto">17%</b></li></ul></div></section>
  </div>
  <section aria-labelledby="ord" style="margin-top:16px"><div class="card-head"><h2 id="ord">Recent orders</h2><a href="#" class="btn btn--sm">View all {icon("chevron")}</a></div>
    <div class="table-wrap"><table><thead><tr><th>Order</th><th>Customer</th><th>Date</th><th class="r">Amount</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></section>
</main></div>"""
    css = "@media (max-width:1100px){#split{grid-template-columns:minmax(0,1fr)!important}}"
    return Screen(
        "dashboard-kpi", "Dashboard: sales KPIs", "A side-navigation finance dashboard: four KPI cards with deltas, a two-series revenue chart, a channel ring and a recent-orders table.",
        "slate", "inter", css, body, ["home", "chart", "card", "users", "box", "settings", "help", "download", "up", "down", "chevron"],
        ["calm", "professional", "light"], ["finance", "sales", "e-commerce", "saas", "admin"], "balanced", uses="the home screen of a business app that answers 'how are we doing' with a few numbers, one trend and the latest records",
        tags=["dashboard", "kpi", "chart", "table"],
    )


def ops_board() -> Screen:
    shipments = [
        ("TRK-20418", "Rotterdam → Leeds", "Hauler 14", "On time", "ok", "92%"),
        ("TRK-20417", "Antwerp → Lyon", "Hauler 07", "Delayed 2 h", "warn", "64%"),
        ("TRK-20412", "Hamburg → Warsaw", "Hauler 22", "On time", "ok", "78%"),
        ("TRK-20409", "Genoa → Zurich", "Hauler 03", "Held at border", "danger", "41%"),
        ("TRK-20405", "Le Havre → Madrid", "Hauler 19", "On time", "ok", "55%"),
    ]
    rows = "".join(
        f'<tr><td class="mono">{i}</td><td><b>{r}</b></td><td class="muted">{h}</td><td><span class="pill pill--{t}">{s}</span></td><td style="min-width:130px"><div class="meter" role="img" aria-label="{p} of the route done"><i style="width:{p}"></i></div></td></tr>'
        for i, r, h, s, t, p in shipments
    )
    bars = bar_chart([94, 91, 96, 88, 93, 97, 90], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], highlight=5, title="On-time delivery by weekday, percent")
    exceptions = [
        ("danger", "Held at border", "TRK-20409 · customs paperwork missing", "12 min ago"),
        ("warn", "Delay", "TRK-20417 · road closure, new ETA 16:40", "34 min ago"),
        ("warn", "Temperature", "TRK-20398 · reefer at 6.1 °C, limit 5 °C", "1 h ago"),
    ]
    items = "".join(
        f'<li><span class="pill pill--{t}" style="flex:none">{h}</span><div style="min-width:0"><div>{d}</div><div class="muted" style="font-size:.85rem">{w}</div></div></li>' for t, h, d, w in exceptions
    )
    body = f"""
<header class="topbar"><div class="brand" style="padding:0"><i>N</i>Northline</div>
<nav aria-label="Primary"><a href="#" aria-current="page">Operations</a><a href="#">Fleet</a><a href="#">Routes</a><a href="#">Billing</a></nav><div class="grow"></div>
<div class="search" style="width:min(260px,30vw)"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Find a shipment" aria-label="Find a shipment"></div>
<button class="btn btn--icon btn--ghost" aria-label="Alerts">{icon("bell")}</button><span class="avatar">SK</span></header>
<main class="main" style="max-width:1280px;margin:0 auto">
  <div class="top"><div><h1>Operations today</h1><p class="sub">Tuesday, 18 March · Rotterdam hub · refreshed every minute</p></div><div class="actions"><button class="btn">{icon("filter")}Region: all</button><button class="btn btn--primary">{icon("plus")}New dispatch</button></div></div>
  <div class="grid cols-4" style="gap:12px">
    <div class="card kpi"><div class="label">In transit</div><div class="value">128</div><span class="muted">across 9 regions</span></div>
    <div class="card kpi"><div class="label">On time</div><div class="value">93.4%</div><span class="delta delta--up">{icon("up")}1.2 pts</span></div>
    <div class="card kpi"><div class="label">Delayed</div><div class="value" style="color:var(--color-warn)">11</div><span class="muted">4 need a decision</span></div>
    <div class="card kpi"><div class="label">Held</div><div class="value" style="color:var(--color-danger)">2</div><span class="muted">customs, border</span></div>
  </div>
  <div class="grid" style="grid-template-columns:minmax(0,3fr) minmax(0,2fr);margin-top:16px" id="split">
    <section aria-labelledby="sh"><div class="card-head"><h2 id="sh">Shipments needing a look</h2><a class="btn btn--sm" href="#">All shipments</a></div>
      <div class="table-wrap"><table><thead><tr><th>Tracking</th><th>Route</th><th>Carrier</th><th>Status</th><th>Progress</th></tr></thead><tbody>{rows}</tbody></table></div></section>
    <section class="card" aria-labelledby="ot"><div class="card-head"><div><h2 id="ot">On-time delivery</h2><p>Last seven days</p></div><span class="pill pill--ok">Target 90%</span></div>{bars}</section>
  </div>
  <section class="card" aria-labelledby="ex" style="margin-top:16px"><div class="card-head"><h2 id="ex">Exceptions</h2><span class="muted">3 open</span></div><ul class="list">{items}</ul></section>
</main>"""
    css = "@media (max-width:1100px){#split{grid-template-columns:minmax(0,1fr)!important}}"
    return Screen(
        "dashboard-ops", "Dashboard: operations board", "A top-navigation operations board: status counters, a shipments table with progress meters, on-time bars and an exceptions list.",
        "harbour", "manrope", css, body, ["search", "bell", "filter", "plus", "up"], ["practical", "calm", "teal"], ["logistics", "operations", "fleet", "support", "field service"], "balanced",
        uses="a live board where someone decides what needs attention now: counters first, then the items that are off plan",
        tags=["dashboard", "status", "table", "top navigation"],
    )


def analytics_dark() -> Screen:
    pages = [("/pricing", "18,420", "4.8%", [4, 6, 5, 8, 7, 9, 11]), ("/docs/getting-started", "15,106", "9.1%", [9, 8, 9, 7, 8, 6, 7]), ("/blog/release-3-2", "9,872", "2.2%", [2, 3, 5, 9, 12, 11, 10]), ("/signup", "7,305", "12.6%", [5, 5, 6, 6, 7, 8, 9])]
    rows = "".join(
        f'<tr><td class="mono">{p}</td><td class="r num">{v}</td><td class="r num">{c}</td><td class="r">{spark([float(x) for x in s], "var(--color-primary)")}</td></tr>' for p, v, c, s in pages
    )
    chart = line_chart(
        [([310, 340, 322, 368, 390, 372, 420, 455, 438, 470], "var(--color-primary)"), ([210, 220, 236, 228, 250, 262, 258, 281, 290, 301], "var(--color-accent2)")],
        ["500", "375", "250", "125", "0"], ["1 Mar", "5 Mar", "10 Mar", "15 Mar", "20 Mar"], height=240, label="Visitors and signups per day",
    )
    funnel = [("Visited the site", "48,210", 100), ("Viewed pricing", "18,420", 38), ("Started signup", "7,305", 15), ("Verified email", "5,118", 11)]
    steps = "".join(
        f'<li style="display:block"><div style="display:flex;justify-content:space-between;margin-bottom:6px"><span>{n}</span><b class="num">{v}</b></div><div class="meter"><i style="width:{w}%"></i></div></li>' for n, v, w in funnel
    )
    body = f"""
<div class="app">
{sidebar("Polarlight", "P", [("chart", "Traffic", ""), ("users", "Audience", ""), ("layers", "Funnels", ""), ("link", "Sources", ""), ("clock", "Realtime", "")], "Traffic", [("Project", [("settings", "Settings", "")])], ("MO", "Mia Ortega", "Growth"))}
<main class="main">
  <div class="top"><div><h1>Traffic</h1><p class="sub">polarlight.app · 1–20 March</p></div><div class="actions"><div class="seg" role="group" aria-label="Range"><button aria-pressed="false">7d</button><button aria-pressed="true">30d</button><button aria-pressed="false">90d</button></div><button class="btn">{icon("filter")}Segment</button></div></div>
  <div class="grid cols-3">
    <article class="card kpi"><div class="label">Visitors</div><div class="value">48,210</div><div style="display:flex;justify-content:space-between;align-items:end"><span class="delta delta--up">{icon("up")}8.2%</span>{spark([20, 24, 22, 28, 31, 29, 36], "var(--color-primary)", 110, 36)}</div></article>
    <article class="card kpi"><div class="label">Signups</div><div class="value">5,118</div><div style="display:flex;justify-content:space-between;align-items:end"><span class="delta delta--up">{icon("up")}12.6%</span>{spark([12, 13, 15, 14, 18, 20, 24], "var(--color-accent2)", 110, 36)}</div></article>
    <article class="card kpi"><div class="label">Bounce rate</div><div class="value">41.7%</div><div style="display:flex;justify-content:space-between;align-items:end"><span class="delta delta--down">{icon("down")}1.4 pts</span>{spark([44, 46, 45, 43, 44, 42, 41], "var(--color-muted)", 110, 36)}</div></article>
  </div>
  <section class="card" style="margin-top:16px" aria-labelledby="t1"><div class="card-head"><div><h2 id="t1">Visitors and signups</h2><p>Per day</p></div><div class="legend"><span><i style="background:var(--color-primary)"></i>Visitors</span><span><i style="background:var(--color-accent2)"></i>Signups</span></div></div>{chart}</section>
  <div class="grid cols-2" style="margin-top:16px;grid-template-columns:minmax(0,3fr) minmax(0,2fr)" id="split">
    <section aria-labelledby="tp"><div class="card-head"><h2 id="tp">Top pages</h2></div><div class="table-wrap"><table><thead><tr><th>Page</th><th class="r">Visitors</th><th class="r">Conversion</th><th class="r">Trend</th></tr></thead><tbody>{rows}</tbody></table></div></section>
    <section class="card" aria-labelledby="fn"><div class="card-head"><h2 id="fn">Signup funnel</h2></div><ul class="list">{steps}</ul></section>
  </div>
</main></div>"""
    css = "@media (max-width:1100px){#split{grid-template-columns:minmax(0,1fr)!important}}"
    return Screen(
        "dashboard-analytics", "Dashboard: analytics (dark)", "A dark analytics screen: range selector, three metrics with sparklines, a two-line chart, a top-pages table with trends and a funnel.",
        "ink", "grotesk", css, body, ["chart", "users", "layers", "link", "clock", "settings", "filter", "up", "down"], ["technical", "focused", "dark"], ["analytics", "growth", "developer tools", "saas", "marketing"], "dense",
        uses="analysis work where the reader compares trends and drills in: dense, dark, numbers first",
        tags=["dashboard", "analytics", "dark", "chart", "funnel"],
    )


def personal_overview() -> Screen:
    schedule = [("08:30", "Stand-up with the support team", "Room 2 · 15 min"), ("10:00", "Review Priya's onboarding draft", "Shared document"), ("13:30", "Customer call: Aster Dental", "Video · 45 min"), ("16:00", "Plan next week", "Focus block")]
    items = "".join(f'<li><b class="mono" style="min-width:56px">{t}</b><div><div>{a}</div><div class="muted" style="font-size:.88rem">{b}</div></div></li>' for t, a, b in schedule)
    ring = lambda pct, label, value: f'<div style="display:flex;gap:14px;align-items:center">{donut([(pct, "var(--color-primary)"), (100 - pct, "transparent")], size=84, thickness=10, centre=f"{pct}%")}<div><b>{label}</b><div class="muted" style="font-size:.88rem">{value}</div></div></div>'  # noqa: E731
    week = bar_chart([3.5, 5, 4, 6.5, 2, 0.5, 1], ["M", "T", "W", "T", "F", "S", "S"], height=120, highlight=3, title="Hours of focus time by day")
    body = f"""
<div class="app">
{sidebar("Tidewell", "T", [("home", "Today", ""), ("calendar", "Week", ""), ("check", "Tasks", "6"), ("star", "Goals", ""), ("chat", "Messages", "2")], "Today", None, ("PN", "Priya Nair", "Customer success"))}
<main class="main" style="max-width:1080px">
  <div class="top"><div><p class="muted" style="font-weight:600">Tuesday, 18 March</p><h1 style="font-size:2.1rem;margin-top:2px">Good morning, Priya</h1><p class="sub">Four things on your calendar and six tasks, two of them due today.</p></div><button class="btn btn--primary">{icon("plus")}Add a task</button></div>
  <div class="grid" style="grid-template-columns:minmax(0,3fr) minmax(0,2fr)" id="split">
    <section class="card" aria-labelledby="sc"><div class="card-head"><h2 id="sc">Today's schedule</h2><a class="btn btn--sm btn--ghost" href="#">Open week {icon("chevron")}</a></div><ul class="list">{items}</ul></section>
    <section class="card" aria-labelledby="gl"><div class="card-head"><h2 id="gl">This week's goals</h2></div>
      <div style="display:grid;gap:18px">{ring(75, "Reply within a day", "30 of 40 conversations")}{ring(40, "Finish onboarding guide", "2 of 5 sections")}{ring(100, "Customer check-ins", "6 of 6 done")}</div></section>
  </div>
  <section class="card" style="margin-top:16px" aria-labelledby="fc"><div class="card-head"><div><h2 id="fc">Focus time</h2><p>You are at 22 hours this week, 3 above your average.</p></div><span class="pill pill--ok">On track</span></div>{week}</section>
</main></div>"""
    css = "@media (max-width:900px){#split{grid-template-columns:minmax(0,1fr)!important}}"
    return Screen(
        "dashboard-personal", "Dashboard: personal day view", "A friendly personal overview: a greeting, today's schedule, progress rings for weekly goals and a focus-time chart.",
        "paper", "nunito", css, body, ["home", "calendar", "check", "star", "chat", "plus", "chevron"], ["warm", "friendly", "light"], ["productivity", "personal", "wellbeing", "education", "customer success"], "airy",
        uses="a person's own start-of-day screen: what is on, what they are working towards, how the week is going",
        tags=["dashboard", "personal", "goals", "calendar"],
    )


ALL = [sales_kpi, ops_board, analytics_dark, personal_overview]
