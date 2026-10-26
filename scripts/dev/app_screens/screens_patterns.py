"""Four office patterns the first ten back-office screens did not have (D-491): a task list grouped by urgency, a hierarchy with a detail panel, a card grid
with progress and budget, and a slide-over drawer form. All follow the office polish rules (D-489): one accent, one recipe for every coloured label, icon chips,
white cards on an off-white page, soft depth."""

from __future__ import annotations

from .kit import icon, sidebar
from .screen import Screen

SPLIT = "@media (max-width:1100px){.split{grid-template-columns:minmax(0,1fr)!important}}"
SHELL = [
    ("home", "Overview", ""),
    ("check", "Tasks", "9"),
    ("users", "People", ""),
    ("layers", "Teams", ""),
    ("file", "Projects", ""),
    ("settings", "Settings", ""),
]
PERSON = ("AN", "Asha Nair", "Operations lead")
TOOLBAR = ".toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:16px 20px;border-bottom:1px solid var(--color-border)}"
COUNT = (
    ".count{display:inline-grid;place-items:center;min-width:22px;padding:0 7px;border-radius:999px;background:var(--hover);"
    "color:var(--color-muted);font-size:.75rem;font-weight:700}"
)


def _header(glyph: str, title: str, sub: str, actions: str) -> str:
    return (
        f'<div class="top"><div style="display:flex;gap:14px;align-items:flex-start"><span class="chip">{icon(glyph)}</span>'
        f'<div><h1>{title}</h1><p class="sub">{sub}</p></div></div><div class="actions">{actions}</div></div>'
    )


def _tile(label: str, value: str, glyph: str, tone: str = "", foot: str = "") -> str:
    modifier = f" chip--{tone}" if tone else ""
    footer = f'<div class="foot">{foot}</div>' if foot else ""
    return (
        f'<div class="card card--lift kpi"><div class="tile"><div><div class="label">{label}</div><div class="value">{value}</div></div>'
        f'<span class="chip{modifier}">{icon(glyph)}</span></div>{footer}</div>'
    )


def _pill(text: str, tone: str = "") -> str:
    return f'<span class="pill{" pill--" + tone if tone else ""}">{text}</span>'


def grouped_tasks() -> Screen:
    groups = [
        (
            "Overdue",
            "danger",
            [
                (
                    "TSK-0412",
                    "Renew the fire safety certificate",
                    ("In progress", "info"),
                    "Compliance",
                    "Dilip Das",
                    ("High", "warn"),
                    "30 Sep",
                ),
                (
                    "TSK-0418",
                    "Schedule the vendor review with Kestrel Components",
                    ("Waiting", "warn"),
                    "Make a call",
                    "Debra Roy",
                    ("Critical", "danger"),
                    "05 Oct",
                ),
                (
                    "TSK-0425",
                    "Send the revised budget to the finance committee",
                    ("In progress", "info"),
                    "Follow up",
                    "Asha Nair",
                    ("High", "warn"),
                    "07 Oct",
                ),
            ],
        ),
        (
            "Due this week",
            "warn",
            [
                (
                    "TSK-0431",
                    "Call Dr. Rao about the site visit on Friday",
                    ("Open", ""),
                    "Make a call",
                    "Sam Ortiz",
                    ("Normal", ""),
                    "09 Oct",
                ),
                (
                    "TSK-0436",
                    "Collect signatures for the lease extension",
                    ("Open", ""),
                    "Paperwork",
                    "Dilip Das",
                    ("Normal", ""),
                    "10 Oct",
                ),
            ],
        ),
    ]
    sections = ""
    for name, tone, tasks in groups:
        rows = ""
        for code, title, status, kind, who, priority, date in tasks:
            alert = " row-alert" if name == "Overdue" else ""
            rows += (
                f'<li class="task{alert}"><div style="min-width:0;flex:1"><div><span class="mono muted" style="font-size:.8rem">{code}</span> <b>{title}</b></div>'
                f'<div class="meta-line">{_pill(*status)}<span class="muted">{kind}</span><span class="who">{icon("users")}{who}</span></div></div>'
                f'<div class="task-end"><span class="num"><b>{date}</b></span>{_pill(*priority)}</div></li>'
            )
        sections += (
            f'<section aria-label="{name}"><div class="group-head">{_pill(name, tone)}<span class="count">{len(tasks)}</span></div>'
            f'<ul class="list task-list">{rows}</ul></section>'
        )
    actions = (
        f'<button class="btn">{icon("clock")}Available now</button><button class="btn">{icon("download")}Export</button>'
        f'<button class="btn btn--primary">{icon("plus")}New task</button>'
    )
    tiles = (
        _tile("Open tasks", "9", "check", "", "Across 4 people")
        + _tile("Overdue", "6", "clock", "danger", "Oldest is 9 days late")
        + _tile("In the manager's queue", "1", "tag", "warn", "Waiting for a decision")
        + _tile("Reminders due", "5", "bell", "ok", "Next one at 15:00")
    )
    body = f"""
<div class="app">
{sidebar("Deskline", "D", SHELL, "Tasks", None, PERSON)}
<main class="main">
  {_header("check", "Tasks", "The office's work list: reminders, follow-ups and delegated work, tracked to completion.", actions)}
  <div class="grid cols-4" style="margin-bottom:16px">{tiles}</div>
  <section class="card" style="padding:0" aria-label="Task list">
    <div class="toolbar"><div class="seg" role="group" aria-label="Show"><button aria-pressed="true">All</button><button aria-pressed="false">Manager's queue<span class="count" style="margin-left:6px">1</span></button></div>
      <div class="search" style="flex:1;min-width:180px;max-width:360px"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search or tag" aria-label="Search tasks"></div>
      <button class="btn">{icon("filter")}Filters<span class="count" style="margin-left:6px">1</span></button></div>
    <div style="padding:6px 20px 20px">{sections}</div>
  </section>
</main></div>"""
    css = (
        TOOLBAR
        + COUNT
        + ".group-head{display:flex;gap:10px;align-items:center;padding:18px 0 8px}"
        + ".task-list li{align-items:center;gap:20px;padding:14px 16px;margin-bottom:8px;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);transition:box-shadow .2s}"
        + ".task-list li:hover{box-shadow:var(--lift,var(--shadow))}.task-list li:last-child{border-bottom:1px solid var(--color-border)}"
        + ".meta-line{display:flex;gap:10px 14px;align-items:center;flex-wrap:wrap;margin-top:6px;font-size:.9rem}.who{display:inline-flex;gap:6px;align-items:center;color:var(--color-muted)}"
        + ".task-end{display:grid;justify-items:end;gap:6px;text-align:right;flex:none}"
        + "@media (max-width:640px){.task-list li{flex-direction:column;align-items:flex-start}.task-end{justify-items:start;text-align:left}}"
    )
    return Screen(
        "grouped-tasks",
        "Tasks: summary tiles and a list grouped by urgency",
        "Four summary tiles with icon chips, a segmented filter with counts, search and filters, and the tasks grouped under Overdue and Due this week with a red bar on late rows, status, type, person, date and priority.",
        "office",
        "inter",
        css,
        body,
        [
            "home",
            "check",
            "users",
            "layers",
            "file",
            "settings",
            "clock",
            "download",
            "plus",
            "tag",
            "bell",
            "search",
            "filter",
        ],
        ["businesslike", "calm", "light"],
        ["tasks", "to-do", "follow-ups", "operations", "case work", "reminders", "back office"],
        "balanced",
        uses="a work list people clear every day: tasks, follow-ups, cases, requests; grouped by how urgent they are",
        tags=["list", "grouped", "summary tiles", "filters", "priority", "overdue", "side navigation"],
    )


def hierarchy_detail() -> Screen:
    tree = [
        (0, "Land Department", "LAND", "HQ, Nabanna", False, False, "#FF7A00"),
        (0, "Panchayat and Rural Development", "P&amp;RD", "Principal Secretary", False, False, "#FF7A00"),
        (0, "Agricultural Marketing", "AGRI", "Secretary Abhinav Sen", True, False, "#FF7A00"),
        (0, "Animal Resource Department", "ARD", "Director's office", False, True, "#FF7A00"),
        (1, "Livestock Development Board", "WBLDB", "Utpal Karmakar", False, False, "#2563EB"),
        (1, "Go Sampad Bivag", "GSB", "Konar Sir", False, False, "#2563EB"),
        (0, "Women and Child Welfare", "W&amp;CD", "Principal Secretary", False, True, "#FF7A00"),
        (1, "ICDS Supply System", "ICDS", "State director", False, False, "#2563EB"),
    ]
    rows = ""
    for depth, name, code, head, selected, has_children, colour in tree:
        chevron = (
            f'<span class="twist">{icon("chevron")}</span>' if has_children else '<span class="twist"></span>'
        )
        weight = ' style="font-size:1rem"' if depth == 0 else ""
        rows += (
            f'<div class="node{" is-selected" if selected else ""}" style="margin-left:{depth * 26}px">{chevron}<span class="dot" style="background:{colour}"></span>'
            f'<div style="min-width:0;flex:1"><div class="node-name"><b{weight}>{name}</b>{_pill(code)}</div>'
            f'<div class="muted node-sub">{icon("users")}{head}</div></div>'
            f'<span class="node-actions"><button class="btn btn--sm btn--icon btn--ghost" aria-label="Edit {name}">{icon("edit")}</button></span></div>'
        )
    notes = [
        (
            "Bills pending from past works",
            "Around 13 crore of bills are pending. What is the fund status, and what are the reasons for the delay?",
            "Added 05 Oct 2026, 06:06 pm",
        ),
        (
            "Urgent recruitment in the department",
            "Executive engineers needed: civil 1, electrical 11. The posts have been vacant for two quarters.",
            "Added 04 Oct 2026, 11:04 pm",
        ),
    ]
    cards = "".join(
        f'<article class="note"><div style="flex:1"><b>{title}</b><p class="muted" style="margin:4px 0 8px">{text}</p><span class="muted" style="font-size:.85rem">{when}</span></div>'
        f'<div class="actions" style="align-items:flex-start;gap:2px"><button class="btn btn--sm btn--icon btn--ghost" aria-label="Edit note">{icon("edit")}</button>'
        f'<button class="btn btn--sm btn--icon btn--ghost" aria-label="Delete note" style="color:var(--color-danger)">{icon("trash")}</button></div></article>'
        for title, text, when in notes
    )
    actions = (
        '<div class="seg" role="group" aria-label="Level"><button aria-pressed="true">State</button><button aria-pressed="false">Central</button></div>'
        f'<button class="btn btn--primary">{icon("plus")}Add department</button>'
    )
    body = f"""
<div class="app">
{sidebar("Deskline", "D", SHELL, "Teams", None, PERSON)}
<main class="main">
  {_header("layers", "Departments", "Government departments serving the region, with their heads and notes.", actions)}
  <div class="grid split" style="grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);align-items:start">
    <section class="card" style="padding:0" aria-label="Department hierarchy"><div class="toolbar" style="padding:12px 16px;gap:8px"><span class="muted" style="letter-spacing:.06em;text-transform:uppercase;font-size:.78rem;font-weight:700">Department hierarchy</span><span style="flex:1"></span><button class="btn btn--sm btn--ghost">Expand all</button><button class="btn btn--sm btn--ghost">Collapse</button></div><div style="padding:10px">{rows}</div></section>
    <section class="card" aria-labelledby="dept">
      <div class="card-head" style="align-items:flex-start;gap:14px"><div style="display:flex;gap:14px;align-items:flex-start"><span class="chip">{icon("layers")}</span><div><h2 id="dept" style="font-size:1.35rem">Agricultural Marketing</h2><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;align-items:center">{_pill("State", "warn")}{_pill("AGRI")}<span class="muted">Passport office and free school street</span></div></div></div><a href="#" class="btn btn--sm">Full details{icon("chevron")}</a></div>
      <div class="tabs" role="tablist" style="margin:6px 0 16px"><a href="#" aria-current="page">Notes<span class="count" style="margin-left:8px">6</span></a><a href="#">Follow-ups<span class="count" style="margin-left:8px">0</span></a><a href="#">Officers and contacts<span class="count" style="margin-left:8px">0</span></a></div>
      <div class="note-head"><span class="chip" style="width:38px;height:38px">{icon("edit")}</span><div style="flex:1"><b>Notes</b><div class="muted" style="font-size:.88rem">Internal department notes</div></div><button class="btn btn--sm btn--icon" aria-label="Add a note">{icon("plus")}</button></div>
      <div class="grid" style="gap:12px">{cards}</div>
    </section>
  </div>
</main></div>"""
    css = (
        SPLIT
        + TOOLBAR
        + COUNT
        + ".node{display:flex;align-items:center;gap:8px;padding:8px 10px 8px 4px;border-radius:12px;margin-bottom:2px}.node:hover{background:var(--hover)}"
        + ".node.is-selected{background:var(--soft);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--color-primary) 18%,transparent)}.node.is-selected b{color:var(--color-primary)}"
        + ".twist{width:22px;display:grid;place-items:center;color:var(--color-muted)}.twist .ico{width:16px;height:16px;transform:rotate(90deg)}"
        + ".dot{width:9px;height:9px;border-radius:999px;flex:none}.node-name{display:flex;gap:8px;align-items:center;flex-wrap:wrap}"
        + ".node-sub{display:flex;gap:6px;align-items:center;font-size:.82rem}.node-sub .ico{width:14px;height:14px}"
        + ".node-actions{opacity:0;transition:opacity .15s}.node:hover .node-actions,.node:focus-within .node-actions{opacity:1}@media (hover:none){.node-actions{opacity:1}}"
        + ".note-head{display:flex;gap:12px;align-items:center;padding:12px 14px;border:1px solid var(--color-border);border-radius:12px;margin-bottom:12px}"
        + ".note{display:flex;gap:12px;padding:14px 16px;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface)}"
    )
    return Screen(
        "hierarchy-detail",
        "Hierarchy: expandable tree with a detail panel",
        "A department tree on the left (a coloured dot for each level, chevrons, code badges, the head of each, edit on hover) and the selected department on the right with a header, tabs with counts and note cards.",
        "office",
        "inter",
        css,
        body,
        ["home", "check", "users", "layers", "file", "settings", "plus", "edit", "trash", "chevron"],
        ["businesslike", "calm", "light"],
        ["organisation", "departments", "hierarchy", "org chart", "directory", "categories", "back office"],
        "balanced",
        uses="browsing a structure and acting on one part of it: departments, teams, accounts, categories, locations, charts of accounts",
        tags=["tree", "hierarchy", "detail panel", "tabs", "notes", "expand collapse", "side navigation"],
    )


def card_grid() -> Screen:
    projects = [
        (
            "Annapurna Swadist Water Plant",
            "Agricultural Marketing",
            ("Planning", "info"),
            0,
            "₹5.00 L",
            "₹0",
            "0%",
            "0",
            "02 Oct 2026",
            "Jalpaiguri",
            "Market Yard",
        ),
        (
            "Dresses for the VCT workers",
            "Panchayat and Rural Development",
            ("Planning", "info"),
            3,
            "₹650.00 Cr",
            "₹19.50 Cr",
            "3%",
            "1,000",
            "23 Oct 2026",
            "Kolkata",
            "",
        ),
        (
            "Management of the Joydev Kenduli fair",
            "Panchayat and Rural Development",
            ("Planning", "info"),
            0,
            "₹50.00 L",
            "₹0",
            "0%",
            "25,00,000",
            "14 Oct 2026",
            "Kolkata",
            "Joydev Kenduli",
        ),
        (
            "Onion quality irregularities",
            "Agricultural Marketing",
            ("In progress", "warn"),
            45,
            "₹12.40 L",
            "₹5.50 L",
            "44%",
            "3,200",
            "30 Nov 2026",
            "Nadia",
            "Quality",
        ),
        (
            "Youth sports hub proposal",
            "Panchayat and Rural Development",
            ("In progress", "warn"),
            82,
            "₹4.80 Cr",
            "₹3.90 Cr",
            "81%",
            "12,500",
            "15 Dec 2026",
            "Howrah",
            "Youth",
        ),
        (
            "Rural road repair, phase two",
            "Public Works",
            ("Completed", "ok"),
            100,
            "₹2.10 Cr",
            "₹2.05 Cr",
            "98%",
            "48,000",
            "01 Sep 2026",
            "Bankura",
            "Roads",
        ),
    ]
    cards = ""
    for name, dept, status, progress, budget, spent, pct, people, date, place, tag in projects:
        colour = (
            "var(--color-ok)"
            if progress >= 80
            else "var(--color-brand)"
            if progress >= 40
            else "var(--color-muted)"
        )
        tag_html = f'<div style="margin:10px 0 12px"><span class="tagchip">{tag}</span></div>' if tag else ""
        cards += (
            f'<article class="card card--lift pcard"><div class="pcard-head"><div style="min-width:0"><b class="clip">{name}</b>'
            f'<div class="muted dept">{icon("layers")}<span class="clip">{dept}</span></div></div>{_pill(*status)}</div>'
            f'<div style="margin-top:14px"><div class="pcard-row"><span class="muted">Progress</span><b class="num">{progress}%</b></div>'
            f'<div class="meter" role="img" aria-label="{progress} percent complete"><i style="width:{progress}%;background:{colour}"></i></div></div>'
            f'<dl class="stats"><div><dt>Budget</dt><dd>{budget}</dd></div><div><dt>Spent ({pct})</dt><dd>{spent}</dd></div>'
            f"<div><dt>Beneficiaries</dt><dd>{people}</dd></div><div><dt>Timeline</dt><dd>{date}</dd></div></dl>"
            f"{tag_html}"
            f'<div class="pcard-foot"><span class="muted dept" style="margin:0">{icon("map")}{place}</span><span class="actions" style="gap:2px">'
            f'<button class="btn btn--sm btn--icon btn--ghost" aria-label="Edit {name}">{icon("edit")}</button>'
            f'<button class="btn btn--sm btn--icon btn--ghost" aria-label="Delete {name}" style="color:var(--color-danger)">{icon("trash")}</button></span></div></article>'
        )
    tiles = (
        _tile("Active projects", "22", "chart", "", "Planning and in progress")
        + _tile("Completed", "9", "check", "ok", "Delivered projects")
        + _tile("Total budget", "₹1,240 Cr", "card", "warn", "Allocated across the portfolio")
        + _tile("Beneficiaries", "3.2 Cr", "users", "", "People reached")
    )
    body = f"""
<div class="app">
{sidebar("Deskline", "D", SHELL, "Projects", None, PERSON)}
<main class="main">
  {_header("file", "Projects", "Track development projects, budgets and delivery.", f'<button class="btn btn--primary">{icon("plus")}New project</button>')}
  <div class="grid cols-4" style="margin-bottom:16px">{tiles}</div>
  <div class="seg" role="group" aria-label="Portfolio" style="margin-bottom:14px"><button aria-pressed="true">Our projects</button><button aria-pressed="false">Partner projects</button></div>
  <section class="card" style="padding:0" aria-label="Projects">
    <div class="toolbar"><div class="search" style="flex:1;min-width:200px;max-width:360px"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search project, department, district, tag" aria-label="Search projects"></div>
      <select class="select" style="width:auto" aria-label="Status"><option>All statuses</option><option>Planning</option><option>In progress</option><option>Completed</option></select>
      <select class="select" style="width:auto" aria-label="Department"><option>All departments</option><option>Agricultural Marketing</option></select>
      <button class="btn">{icon("download")}Export</button><div class="seg" role="group" aria-label="View"><button aria-pressed="false" aria-label="Table view">{icon("file")}</button><button aria-pressed="true" aria-label="Card view">{icon("grid")}</button></div></div>
    <div class="pgrid">{cards}</div>
  </section>
</main></div>"""
    css = (
        TOOLBAR
        + ".pgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;padding:20px}"
        + "@media (max-width:1180px){.pgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media (max-width:760px){.pgrid{grid-template-columns:minmax(0,1fr)}}"
        + ".pcard{display:flex;flex-direction:column;padding:18px}.pcard-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}"
        + ".clip{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        + ".dept{display:flex;gap:6px;align-items:center;font-size:.85rem;margin-top:3px;min-width:0}.dept .ico{width:14px;height:14px}"
        + ".pcard-row{display:flex;justify-content:space-between;font-size:.8rem;font-weight:600;margin-bottom:6px}.meter{height:6px}"
        + ".stats{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0}.stats dt{color:var(--color-muted);font-size:.8rem}.stats dd{margin:2px 0 0;font-weight:700;font-variant-numeric:tabular-nums}"
        + ".pcard-foot{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:12px;border-top:1px solid var(--color-border)}"
        + ".tagchip{display:inline-block;padding:2px 10px;border-radius:8px;font-size:.8rem;font-weight:600;background:color-mix(in srgb,#7c3aed 12%,var(--color-surface));color:#5b21b6;box-shadow:inset 0 0 0 1px color-mix(in srgb,#7c3aed 22%,transparent)}"
    )
    return Screen(
        "card-grid",
        "Cards: portfolio grid with progress and budget",
        "Summary tiles, a segmented portfolio switch, search with status and department filters and a table or card toggle, then a grid of cards: name, department, status, progress meter, budget against spent, people, timeline, place, tag and edit or delete.",
        "office",
        "inter",
        css,
        body,
        [
            "home",
            "check",
            "users",
            "layers",
            "file",
            "settings",
            "plus",
            "chart",
            "card",
            "search",
            "download",
            "grid",
            "map",
            "edit",
            "trash",
        ],
        ["businesslike", "calm", "light"],
        ["projects", "portfolio", "budget", "programmes", "delivery tracking", "grants", "back office"],
        "balanced",
        uses="comparing many things that each have a status, a budget and progress: projects, programmes, grants, campaigns, sites",
        tags=["cards", "grid", "progress", "budget", "filters", "view toggle", "side navigation"],
    )


def drawer_form() -> Screen:
    rows = [
        ("Annapurna Swadist Water Plant", "Agricultural Marketing", "info", "Planning", "₹5.00 L"),
        ("Onion quality irregularities", "Agricultural Marketing", "warn", "In progress", "₹12.40 L"),
        ("Rural road repair, phase two", "Public Works", "ok", "Completed", "₹2.10 Cr"),
        ("Youth sports hub proposal", "Panchayat and Rural Development", "warn", "In progress", "₹4.80 Cr"),
    ]
    behind = "".join(
        f'<tr><td><b>{n}</b><div class="muted" style="font-size:.85rem">{d}</div></td><td>{_pill(s, t)}</td><td class="r num">{a}</td></tr>'
        for n, d, t, s, a in rows
    )
    body = f"""
<div class="app">
{sidebar("Deskline", "D", SHELL, "Projects", None, PERSON)}
<main class="main" aria-hidden="true">
  {_header("file", "Projects", "Track development projects, budgets and delivery.", f'<button class="btn btn--primary">{icon("plus")}New project</button>')}
  <div class="table-wrap"><table><thead><tr><th>Project</th><th>Status</th><th class="r">Budget</th></tr></thead><tbody>{behind}</tbody></table></div>
</main></div>
<div class="scrim" aria-hidden="true"></div>
<aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="dt">
  <header class="drawer-head"><div style="min-width:0"><h2 id="dt" style="font-size:1.25rem">New project</h2><p class="muted" style="margin-top:2px">Register a development project to track budget and delivery</p></div>
    <div class="actions" style="gap:2px"><button class="btn btn--sm btn--icon btn--ghost" aria-label="Expand to full screen">{icon("grid")}</button><button class="btn btn--sm btn--icon btn--ghost" aria-label="Close">{icon("x")}</button></div></header>
  <div class="drawer-body">
    <section class="fold" aria-labelledby="f1"><button class="fold-head" aria-expanded="true"><span id="f1">Project details</span>{icon("chevron")}</button>
      <div class="fold-body">
        <div class="field"><label for="pn">Project name <span style="color:var(--color-danger)">*</span></label><input class="input" id="pn" placeholder="e.g. Piped water, Semiliguda"></div>
        <div class="field"><label for="ov">Overview</label><textarea class="textarea" id="ov" placeholder="What is this project about?"></textarea><span class="hint">A short summary of the project</span></div>
        <div class="grid cols-2"><div class="field"><label for="dp">Department</label><select class="select" id="dp"><option>Unassigned</option><option>Agricultural Marketing</option></select><span class="hint">Groups the project under Our projects when it is your own</span></div>
          <div class="field"><label for="og">Associated organisation</label><input class="input" id="og" placeholder="Type to search or press Enter to add"><span class="hint">Links the project to a directory organisation</span></div></div>
        <div class="field"><label for="st">Status</label><select class="select" id="st"><option>Planning</option><option>In progress</option><option>On hold</option><option>Completed</option></select></div>
      </div></section>
    <section class="fold is-closed"><button class="fold-head" aria-expanded="false"><span>Budget and delivery</span>{icon("chevron")}</button></section>
    <section class="fold is-closed"><button class="fold-head" aria-expanded="false"><span>Location</span>{icon("chevron")}</button></section>
  </div>
  <footer class="drawer-foot"><button class="btn">Cancel</button><button class="btn btn--primary">Create project</button></footer>
</aside>"""
    css = (
        ".scrim{position:fixed;inset:0;background:rgba(15,23,42,.5);backdrop-filter:blur(3px);z-index:20}"
        ".drawer{position:fixed;top:0;right:0;bottom:0;width:min(580px,100vw);background:var(--color-surface);z-index:30;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.18)}"
        ".drawer-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;padding:18px 24px;border-bottom:1px solid var(--color-border)}"
        ".drawer-body{flex:1;overflow-y:auto;padding:20px 24px;display:grid;gap:14px;align-content:start}"
        ".fold{border:1px solid var(--color-border);border-radius:14px;overflow:hidden}"
        ".fold-head{display:flex;justify-content:space-between;align-items:center;width:100%;padding:14px 16px;border:0;background:var(--soft);color:var(--color-ink);font-weight:700;font-size:.78rem;letter-spacing:.07em;text-transform:uppercase;cursor:pointer}"
        ".fold-head .ico{transform:rotate(-90deg);color:var(--color-muted)}.fold-head[aria-expanded=false] .ico{transform:rotate(90deg)}.fold.is-closed .fold-head{background:var(--color-surface)}"
        ".fold-body{display:grid;gap:16px;padding:18px 16px 20px}"
        ".drawer-foot{display:flex;justify-content:flex-end;gap:10px;padding:14px 24px calc(14px + env(safe-area-inset-bottom,0px));border-top:1px solid var(--color-border);background:var(--hover)}"
        "@media (max-width:860px){.drawer .grid.cols-2{grid-template-columns:minmax(0,1fr)}}"
    )
    return Screen(
        "drawer-form",
        "Form: slide-over drawer over a list",
        "A list page dimmed behind a scrim, and a drawer from the right with a title, an expand button, collapsible sections (the first open, the others closed), fields with hints and a sticky footer with Cancel and the main action.",
        "office",
        "inter",
        css,
        body,
        ["home", "check", "users", "layers", "file", "settings", "plus", "x", "grid", "chevron"],
        ["businesslike", "calm", "light"],
        ["forms", "create", "edit record", "drawer", "side panel", "modal form", "back office"],
        "balanced",
        uses="creating or editing a record without leaving the list: new project, new contact, new ticket; long forms folded into sections",
        tags=[
            "drawer",
            "slide-over",
            "form",
            "collapsible sections",
            "sticky footer",
            "scrim",
            "side navigation",
        ],
    )


ALL = [grouped_tasks, hierarchy_detail, card_grid, drawer_form]
