"""Two list patterns from the WordPress admin study (docs/WORDPRESS_STUDY.md, BO10 and BO11, D-495): a list with status links, row actions, a bulk bar and a column menu,
and a collection with a table, grid and list view switch. Office polish (D-489): one accent, one recipe for every coloured label, icon chips, soft depth."""

from __future__ import annotations

from .kit import icon, sidebar
from .screen import Screen

SHELL = [
    ("home", "Overview", ""),
    ("file", "Invoices", "42"),
    ("users", "Customers", ""),
    ("box", "Products", ""),
    ("chart", "Reports", ""),
    ("settings", "Settings", ""),
]
PERSON = ("AN", "Asha Nair", "Finance lead")
COUNT = (
    ".count{display:inline-grid;place-items:center;min-width:22px;padding:0 7px;border-radius:999px;background:var(--hover);"
    "color:var(--color-muted);font-size:.75rem;font-weight:700}"
)
TOOLBAR = ".toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:14px 20px;border-bottom:1px solid var(--color-border)}"


def _header(glyph: str, title: str, sub: str, actions: str) -> str:
    return (
        f'<div class="top"><div style="display:flex;gap:14px;align-items:flex-start"><span class="chip">{icon(glyph)}</span>'
        f'<div><h1>{title}</h1><p class="sub">{sub}</p></div></div><div class="actions">{actions}</div></div>'
    )


def _pill(text: str, tone: str = "") -> str:
    return f'<span class="pill{" pill--" + tone if tone else ""}">{text}</span>'


def list_bulk() -> Screen:
    rows = [
        (
            "INV-2041",
            "Kestrel Components",
            "Supply of 40 bearings",
            ("Overdue", "danger"),
            "₹1,84,000",
            "28 Sep",
            True,
        ),
        (
            "INV-2042",
            "Northfield Dairy",
            "October milk contract",
            ("Sent", "info"),
            "₹62,500",
            "12 Oct",
            False,
        ),
        (
            "INV-2043",
            "Rao & Sons",
            "Site survey, phase two",
            ("Overdue", "danger"),
            "₹3,10,000",
            "30 Sep",
            True,
        ),
        ("INV-2044", "Tiger Hill Tea", "Packaging run", ("Draft", ""), "₹48,200", "—", False),
        ("INV-2045", "Greenline Logistics", "Freight, week 39", ("Paid", "ok"), "₹91,750", "25 Sep", False),
        (
            "INV-2046",
            "Meera Textiles",
            "Fabric order #118",
            ("Overdue", "danger"),
            "₹2,25,400",
            "01 Oct",
            True,
        ),
    ]
    body_rows = ""
    for code, who, note, status, amount, due, selected in rows:
        checked = " checked" if selected else ""
        body_rows += (
            f'<tr{" class=selected" if selected else ""}><td style="width:44px"><input type="checkbox" aria-label="Select {code}"{checked} style="width:18px;height:18px;accent-color:var(--color-primary)"></td>'
            f'<td><div class="cell-main"><div><b>{who}</b><span class="mono">{code}</span> · <span>{note}</span>'
            f'<div class="row-actions"><a href="#">View</a><a href="#">Quick edit</a><a href="#">Send reminder</a><a href="#" class="danger">Delete</a></div></div></div></td>'
            f'<td>{_pill(*status)}</td><td class="r num"><b>{amount}</b></td><td class="num">{due}</td></tr>'
        )
    status_links = "".join(
        f'<a href="#"{" aria-current=page" if current else ""}>{name}<span class="count">{count}</span></a>'
        for name, count, current in (
            ("All", 42, True),
            ("Draft", 6, False),
            ("Sent", 21, False),
            ("Overdue", 9, False),
            ("Paid", 6, False),
        )
    )
    actions = f'<button class="btn">{icon("download")}Export</button><button class="btn btn--primary">{icon("plus")}New invoice</button>'
    body = f"""
<div class="app">
{sidebar("Ledgerline", "L", SHELL, "Invoices", None, PERSON)}
<main class="main">
  {_header("file", "Invoices", "Everything billed, sent and still owed. Pick rows to act on several at once.", actions)}
  <div class="notice" role="status">{icon("check")}<div><b>3 reminders sent.</b> The customers were emailed at 10:42.</div><button class="btn btn--ghost" aria-label="Dismiss">{icon("x")}</button></div>
  <section class="card" style="padding:0" aria-label="Invoice list">
    <nav class="tabs" aria-label="Status">{status_links}</nav>
    <div class="toolbar">
      <div class="search" style="flex:1;min-width:180px;max-width:340px"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search invoices" aria-label="Search invoices"></div>
      <button class="btn">{icon("filter")}Filters</button>
      <details class="menu"><summary class="btn">{icon("grid")}Columns</summary><div class="popover"><label class="check"><input type="checkbox" checked>Customer</label><label class="check"><input type="checkbox" checked>Status</label><label class="check"><input type="checkbox" checked>Amount</label><label class="check"><input type="checkbox" checked>Due</label><label class="check"><input type="checkbox">Owner</label></div></details>
      <label class="muted" style="margin-left:auto;font-size:.9rem">Rows <select class="input" style="width:auto;display:inline-block" aria-label="Rows per page"><option>25</option><option>50</option></select></label>
    </div>
    <div class="bulk" role="region" aria-label="Selected rows"><b>3 selected</b><span class="muted">₹7,19,400 in total</span>
      <span class="bulk-actions"><button class="btn">{icon("send")}Send reminder</button><button class="btn">{icon("users")}Reassign</button><button class="btn btn--danger">{icon("trash")}Delete</button></span>
      <button class="btn btn--ghost" style="margin-left:auto">Clear selection</button></div>
    <div class="table-wrap" style="border:0;border-radius:0"><table>
      <thead><tr><th><input type="checkbox" aria-label="Select all" style="width:18px;height:18px;accent-color:var(--color-primary)"></th><th>Customer</th><th>Status</th><th class="r">Amount</th><th>Due</th></tr></thead>
      <tbody>{body_rows}</tbody></table></div>
    <div class="pager" style="padding:12px 20px"><span>Showing 1 to 6 of 42</span><span class="seg" role="group" aria-label="Pages"><button aria-pressed="true">1</button><button aria-pressed="false">2</button><button aria-pressed="false">3</button></span></div>
  </section>
</main></div>"""
    css = (
        TOOLBAR
        + COUNT
        + ".notice{display:flex;gap:12px;align-items:center;padding:12px 16px;margin-bottom:16px;border-radius:12px;background:color-mix(in srgb,var(--color-ok) 10%,var(--color-surface));color:var(--color-ink);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--color-ok) 30%,transparent)}.notice .ico{color:var(--color-ok);flex:none}.notice .btn{margin-left:auto}"
        + ".card>.tabs{padding:0 12px}"
        + ".bulk{display:flex;gap:12px 16px;align-items:center;flex-wrap:wrap;padding:10px 20px;background:var(--soft);border-bottom:1px solid var(--color-border)}.bulk-actions{display:inline-flex;gap:8px;flex-wrap:wrap}"
        + "tr.selected{background:var(--soft)}"
        + ".row-actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:4px;font-size:.85rem;opacity:0;transition:opacity .15s}.row-actions a{color:var(--color-primary);text-decoration:none}.row-actions a:hover{text-decoration:underline}.row-actions .danger{color:var(--color-danger)}"
        + "tr:hover .row-actions,tr:focus-within .row-actions{opacity:1}@media (hover:none){.row-actions{opacity:1}}"
        + ".menu{position:relative}.menu summary{list-style:none;cursor:pointer}.menu summary::-webkit-details-marker{display:none}.popover{position:absolute;z-index:5;top:calc(100% + 6px);left:0;min-width:180px;display:grid;gap:10px;padding:14px;border-radius:12px;background:var(--color-surface);border:1px solid var(--color-border);box-shadow:var(--lift,var(--shadow))}"
        + "@media (max-width:640px){.bulk-actions{width:100%}.bulk .btn--ghost{margin-left:0!important}}"
    )
    return Screen(
        "list-bulk",
        "List with status links, row actions and a bulk bar",
        "Status links with counts above a list, a dismissible notice, search, filters and a column menu, hover row actions (always shown on touch), checkboxes with a bulk bar that names the selection and its total, and a pager.",
        "office",
        "inter",
        css,
        body,
        [
            "home",
            "file",
            "users",
            "box",
            "chart",
            "settings",
            "check",
            "x",
            "search",
            "filter",
            "grid",
            "send",
            "trash",
            "download",
            "plus",
        ],
        ["businesslike", "calm", "light"],
        ["list", "invoices", "orders", "records", "bulk actions", "back office", "admin"],
        "balanced",
        uses="any long list people work through in bulk: invoices, orders, contacts, content; with filters by state and actions on many rows",
        tags=[
            "list",
            "status links",
            "bulk actions",
            "row actions",
            "columns menu",
            "notice",
            "pager",
            "side navigation",
        ],
    )


def collection_switch() -> Screen:
    items = [
        ("Annual report 2026", "PDF · 4.2 MB", "Finance", ("Final", "ok"), "file"),
        ("Site survey photos", "Folder · 38 files", "Operations", ("Review", "warn"), "layers"),
        ("Vendor contract, Kestrel", "Document · 12 pages", "Legal", ("Draft", ""), "file"),
        ("Q3 stock count", "Sheet · 214 rows", "Warehouse", ("Final", "ok"), "chart"),
        ("Brand guidelines", "Document · 24 pages", "Marketing", ("Review", "warn"), "star"),
        ("Staff handbook", "Document · 41 pages", "People", ("Final", "ok"), "users"),
        ("Fleet maintenance plan", "Sheet · 60 rows", "Operations", ("Draft", ""), "truck"),
        ("Safety audit, Pune", "PDF · 2.1 MB", "Compliance", ("Overdue", "danger"), "shield"),
    ]
    cards = "".join(
        f'<article class="card card--lift item"><div class="thumb"><span class="chip">{icon(glyph)}</span></div>'
        f'<div class="item-body"><b>{name}</b><div class="muted" style="font-size:.88rem">{meta}</div>'
        f'<div class="item-foot">{_pill(*status)}<span class="muted" style="font-size:.85rem">{team}</span></div></div></article>'
        for name, meta, team, status, glyph in items
    )
    actions = f'<button class="btn">{icon("download")}Export</button><button class="btn btn--primary">{icon("plus")}Add document</button>'
    body = f"""
<div class="app">
{sidebar("Folio", "F", [("home", "Overview", ""), ("file", "Documents", "128"), ("users", "Teams", ""), ("star", "Starred", "5"), ("settings", "Settings", "")], "Documents", None, ("AN", "Asha Nair", "Office manager"))}
<main class="main">
  {_header("file", "Documents", "Everything the office keeps, as a grid, a table or a list. The view you pick is remembered.", actions)}
  <section class="card" style="padding:0" aria-label="Document collection">
    <div class="toolbar">
      <div class="search" style="flex:1;min-width:180px;max-width:340px"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg><input class="input" placeholder="Search documents" aria-label="Search documents"></div>
      <div class="seg" role="group" aria-label="Team"><button aria-pressed="true">All</button><button aria-pressed="false">Finance</button><button aria-pressed="false">Operations</button><button aria-pressed="false">Legal</button></div>
      <label class="muted" style="font-size:.9rem">Sort <select class="input" style="width:auto;display:inline-block" aria-label="Sort"><option>Recently updated</option><option>Name</option><option>Status</option></select></label>
      <div class="seg view-switch" role="group" aria-label="View" style="margin-left:auto"><button aria-pressed="false" aria-label="Table view">{icon("filter")}</button><button aria-pressed="true" aria-label="Grid view">{icon("grid")}</button><button aria-pressed="false" aria-label="List view">{icon("layers")}</button></div>
    </div>
    <div class="collection" style="padding:20px">{cards}</div>
    <div class="pager" style="padding:0 20px 16px"><span>Showing 8 of 128</span><span class="seg" role="group" aria-label="Pages"><button aria-pressed="true">1</button><button aria-pressed="false">2</button><button aria-pressed="false">3</button></span></div>
  </section>
</main></div>"""
    css = (
        TOOLBAR
        + COUNT
        + ".collection{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}"
        + ".item{padding:0;overflow:hidden;display:flex;flex-direction:column}.thumb{display:grid;place-items:center;height:110px;background:var(--soft);border-bottom:1px solid var(--color-border)}"
        + ".item-body{display:grid;gap:4px;padding:14px 16px 16px}.item-foot{display:flex;gap:10px;align-items:center;justify-content:space-between;margin-top:8px}"
        + ".view-switch button{display:grid;place-items:center;width:36px;height:32px;padding:0}.view-switch .ico{width:18px;height:18px}"
        + "@media (max-width:640px){.view-switch{margin-left:0!important}.collection{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}}"
    )
    return Screen(
        "collection-switch",
        "Collection with a table, grid and list view switch",
        "A document collection shown as cards with a thumbnail, status and team, a switch between table, grid and list in the toolbar, team filter, sort and search, and a pager.",
        "office",
        "inter",
        css,
        body,
        [
            "home",
            "file",
            "users",
            "star",
            "settings",
            "layers",
            "chart",
            "truck",
            "shield",
            "search",
            "filter",
            "grid",
            "download",
            "plus",
        ],
        ["businesslike", "calm", "light"],
        ["collection", "documents", "files", "gallery", "catalogue", "view switch", "back office"],
        "balanced",
        uses="a set of things people browse and sometimes compare: documents, products, projects, media; seen as cards or as rows",
        tags=["collection", "grid", "view switch", "filters", "sort", "cards", "side navigation"],
    )


ALL = [list_bulk, collection_switch]
