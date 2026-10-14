"""Four settings screens: account with API keys, a notification matrix, plan and billing, and roles with a permission grid (D-366)."""

from __future__ import annotations

from .kit import icon, sidebar
from .screen import Screen

SPLIT = "@media (max-width:1000px){#split{grid-template-columns:minmax(0,1fr)!important}.setnav{display:flex;overflow-x:auto;gap:4px}.setnav a{white-space:nowrap}}"
SETNAV_CSS = (
    ".setnav{display:grid;gap:2px;align-content:start}.setnav a{padding:9px 12px;border-radius:var(--r);color:var(--color-muted);text-decoration:none;font-weight:500}"
    ".setnav a:hover{background:var(--hover);color:var(--color-ink)}.setnav a[aria-current=page]{background:var(--soft);color:var(--color-ink);font-weight:600}"
    ".srow{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:16px 0;border-bottom:1px solid var(--color-border)}.srow:last-child{border-bottom:0}.srow p{color:var(--color-muted);font-size:.9rem;margin-top:2px}"
)


def _setnav(current: str, items: list[str]) -> str:
    return "".join(f'<a href="#"{" aria-current=page" if i == current else ""}>{i}</a>' for i in items)


def account() -> Screen:
    nav = _setnav("Account", ["Account", "Security", "Notifications", "Billing", "Integrations"])
    keys = [("Production server", "sk_live_••••8f2c", "Created 3 Feb · used 2 min ago"), ("Staging", "sk_test_••••19ab", "Created 20 Jan · used yesterday"), ("Data export script", "sk_live_••••c07d", "Created 9 Dec · never used")]
    krows = "".join(
        f'<li style="justify-content:space-between;gap:16px;flex-wrap:wrap"><div><b>{n}</b><div class="muted" style="font-size:.88rem">{u}</div></div><div class="actions"><code class="mono" style="background:var(--hover);padding:3px 8px;border-radius:6px;font-size:.88rem">{v}</code><button class="btn btn--sm">Copy</button><button class="btn btn--sm btn--danger">Revoke</button></div></li>'
        for n, v, u in keys
    )
    body = f"""
<div class="app">
{sidebar("Relay", "R", [("home", "Home", ""), ("link", "Webhooks", ""), ("chart", "Logs", ""), ("key", "API keys", ""), ("settings", "Settings", "")], "Settings", None, ("TO", "Tobias Ortiz", "Owner"))}
<main class="main" style="max-width:1080px">
  <div class="top"><div><h1>Settings</h1><p class="sub">Manage your profile, security and API access.</p></div></div>
  <div class="grid" style="grid-template-columns:200px minmax(0,1fr);align-items:start;gap:28px" id="split">
    <nav class="setnav" aria-label="Settings">{nav}</nav>
    <div style="display:grid;gap:18px">
      <section class="card" aria-labelledby="pf"><div class="card-head"><div><h2 id="pf">Profile</h2><p>Shown to teammates and on invoices.</p></div></div>
        <div style="display:flex;gap:18px;align-items:center;margin-bottom:18px;flex-wrap:wrap"><span class="avatar" style="width:64px;height:64px;font-size:1.2rem">TO</span><div class="actions"><button class="btn btn--sm">Upload a photo</button><button class="btn btn--sm btn--ghost">Remove</button></div></div>
        <div class="grid cols-2" style="gap:16px"><div class="field"><label for="n">Full name</label><input class="input" id="n" value="Tobias Ortiz"></div><div class="field"><label for="e">Email</label><input class="input" id="e" type="email" value="tobias@relay.example"></div>
        <div class="field"><label for="tz">Time zone</label><select class="select" id="tz"><option>Europe/Lisbon (UTC+0)</option><option>America/New_York</option></select></div><div class="field"><label for="lg">Language</label><select class="select" id="lg"><option>English</option><option>Português</option></select></div></div>
        <div class="actions" style="justify-content:flex-end;margin-top:18px"><button class="btn">Cancel</button><button class="btn btn--primary">Save changes</button></div></section>
      <section class="card" aria-labelledby="sc"><div class="card-head"><div><h2 id="sc">Security</h2><p>Protect the account and its keys.</p></div></div>
        <div class="srow"><div><b>Two-step verification</b><p>Ask for a code from an authenticator app at sign-in.</p></div><label class="switch"><input type="checkbox" checked aria-label="Two-step verification"><span></span></label></div>
        <div class="srow"><div><b>Sign out other devices when the password changes</b><p>Recommended.</p></div><label class="switch"><input type="checkbox" checked aria-label="Sign out other devices"><span></span></label></div>
        <div class="srow"><div><b>Email me about new sign-ins</b><p>Only from devices or countries we have not seen.</p></div><label class="switch"><input type="checkbox" aria-label="Email about new sign-ins"><span></span></label></div></section>
      <section class="card" aria-labelledby="ak"><div class="card-head"><div><h2 id="ak">API keys</h2><p>Keys carry the permissions of the owner.</p></div><button class="btn btn--sm btn--primary">{icon("plus")}Create key</button></div><ul class="list">{krows}</ul></section>
      <section class="card" aria-labelledby="dz" style="border-color:color-mix(in srgb,var(--color-danger) 40%,var(--color-border))"><div class="srow" style="padding:0"><div><h2 id="dz" style="color:var(--color-danger)">Delete this workspace</h2><p>Removes all projects, logs and keys after 14 days. This cannot be undone.</p></div><button class="btn btn--danger">Delete workspace</button></div></section>
    </div>
  </div>
</main></div>"""
    return Screen(
        "settings-account", "Settings: account, security and API keys", "A settings page with a vertical section menu, a profile form, toggle rows, an API key list with copy and revoke, and a separated danger zone.",
        "slate", "inter", SETNAV_CSS + SPLIT, body, ["home", "link", "chart", "key", "settings", "plus"], ["clear", "calm", "light"], ["developer tools", "saas", "admin", "account"], "balanced",
        uses="the settings of any product: profile, security, keys; the section menu, setting rows with switches and the danger zone are the pattern",
        tags=["settings", "toggles", "api keys", "forms", "side navigation"],
    )


def notifications() -> Screen:
    events = [("A task is assigned to me", True, True, False), ("Someone mentions me", True, True, True), ("A deadline is tomorrow", True, False, True), ("Weekly summary", False, True, False), ("Billing and security notices", True, True, False)]
    rows = "".join(
        f'<tr><td><b>{n}</b></td>' + "".join(f'<td class="r" style="text-align:center"><label class="switch" style="display:inline-block"><input type="checkbox"{" checked" if v else ""} aria-label="{n}, {c}"><span></span></label></td>' for v, c in zip((a, b, c2), ("email", "mobile push", "text message"), strict=True)) + "</tr>"
        for n, a, b, c2 in events
    )
    body = f"""
<header class="topbar"><div class="brand" style="padding:0"><i>O</i>Orbit</div><nav aria-label="Primary"><a href="#">Projects</a><a href="#">Inbox</a><a href="#" aria-current="page">Settings</a></nav><div class="grow"></div><span class="avatar">NK</span></header>
<main class="main" style="max-width:900px;margin:0 auto">
  <div class="top"><div><h1>Notifications</h1><p class="sub">Choose what reaches you, and where.</p></div></div>
  <section class="card" aria-labelledby="mx" style="padding:0;overflow:hidden"><div style="padding:20px 20px 4px"><h2 id="mx">What to send</h2><p class="muted" style="margin-top:2px">Changes save automatically.</p></div>
    <div class="table-wrap" style="border:0;border-radius:0"><table><thead><tr><th>When</th><th style="text-align:center">Email</th><th style="text-align:center">Mobile push</th><th style="text-align:center">Text</th></tr></thead><tbody>{rows}</tbody></table></div></section>
  <div class="grid cols-2" style="margin-top:18px">
    <section class="card" aria-labelledby="qh"><h2 id="qh">Quiet hours</h2><p class="muted" style="margin:4px 0 16px">No push or text during these hours. Email still arrives.</p>
      <div class="srow" style="padding-top:0"><b>Pause overnight</b><label class="switch"><input type="checkbox" checked aria-label="Pause overnight"><span></span></label></div>
      <div class="grid cols-2" style="gap:12px;margin-top:6px"><div class="field"><label for="f">From</label><input class="input mono" id="f" value="21:00"></div><div class="field"><label for="t">Until</label><input class="input mono" id="t" value="07:30"></div></div></section>
    <section class="card" aria-labelledby="dg"><h2 id="dg">Daily digest</h2><p class="muted" style="margin:4px 0 16px">One email instead of many.</p>
      <div class="field"><label for="dd">Send at</label><select class="select" id="dd"><option>08:00 each weekday</option><option>17:00 each weekday</option><option>Never</option></select></div>
      <div class="srow" style="margin-top:8px"><div><b>Include quiet projects</b><p>Projects with no activity.</p></div><label class="switch"><input type="checkbox" aria-label="Include quiet projects"><span></span></label></div></section>
  </div>
</main>"""
    return Screen(
        "settings-notifications", "Settings: notification preferences", "A preference matrix of events against channels with switches, plus quiet hours with time fields and a digest schedule.",
        "paper", "dmserif", SETNAV_CSS, body, ["plus"], ["calm", "considerate", "light"], ["productivity", "communication", "collaboration", "mobile app"], "airy",
        uses="letting people choose what they are told and how; the switch matrix keeps many choices scannable",
        tags=["settings", "matrix", "toggles", "top navigation"],
    )


def billing() -> Screen:
    usage = [("Seats", "18 of 25", 72), ("Storage", "142 of 200 GB", 71), ("API calls", "410k of 500k", 82)]
    meters = "".join(f'<div><div style="display:flex;justify-content:space-between;margin-bottom:6px"><span>{n}</span><b class="num">{v}</b></div><div class="meter" role="img" aria-label="{n} {p} percent used"><i style="width:{p}%"></i></div></div>' for n, v, p in usage)
    inv = [("INV-2025-03", "1 Mar 2025", "$432.00", "Paid"), ("INV-2025-02", "1 Feb 2025", "$432.00", "Paid"), ("INV-2025-01", "1 Jan 2025", "$398.00", "Paid")]
    rows = "".join(f'<tr><td class="mono">{a}</td><td class="muted">{b}</td><td class="r num">{c}</td><td><span class="pill pill--ok">{d}</span></td><td class="r"><a href="#">PDF</a></td></tr>' for a, b, c, d in inv)
    body = f"""
<div class="app">
{sidebar("Relay", "R", [("home", "Home", ""), ("link", "Webhooks", ""), ("chart", "Logs", ""), ("settings", "Settings", "")], "Settings", [("Settings", [("users", "Team", ""), ("card", "Plan and billing", ""), ("shield", "Security", "")])], ("TO", "Tobias Ortiz", "Owner"))}
<main class="main" style="max-width:1080px">
  <div class="top"><div><h1>Plan and billing</h1><p class="sub">Next invoice on 1 April · $432.00</p></div><button class="btn">{icon("download")}Download all invoices</button></div>
  <div class="grid" style="grid-template-columns:minmax(0,3fr) minmax(0,2fr)" id="split">
    <section class="card" aria-labelledby="pl"><div class="card-head"><div><span class="pill pill--info">Current plan</span><h2 id="pl" style="font-size:1.5rem;margin-top:10px">Growth</h2><p>$24 per seat per month, billed monthly</p></div><button class="btn btn--primary">Change plan</button></div>
      <div style="display:grid;gap:18px;margin-top:8px">{meters}</div><p class="muted" style="margin-top:16px;font-size:.9rem">API calls reset on 1 April. At 100% calls are slowed, never stopped.</p></section>
    <section class="card" aria-labelledby="pm"><h2 id="pm">Payment method</h2>
      <div style="display:flex;gap:14px;align-items:center;margin:16px 0"><span class="avatar" style="border-radius:10px;width:46px;height:32px">{icon("card")}</span><div><b>Visa ending 4242</b><div class="muted" style="font-size:.88rem">Expires 08/27</div></div></div>
      <div class="actions"><button class="btn btn--sm">Update card</button><button class="btn btn--sm btn--ghost">Add another</button></div>
      <hr class="divider"><div class="field"><label for="be">Send invoices to</label><input class="input" id="be" value="finance@relay.example"></div></section>
  </div>
  <section aria-labelledby="iv" style="margin-top:18px"><div class="card-head"><h2 id="iv">Invoices</h2></div><div class="table-wrap"><table><thead><tr><th>Invoice</th><th>Date</th><th class="r">Amount</th><th>Status</th><th class="r"><span class="sr">Download</span></th></tr></thead><tbody>{rows}</tbody></table></div></section>
</main></div>"""
    return Screen(
        "settings-billing", "Settings: plan, usage and invoices", "A billing page with the current plan, usage meters against limits, a payment method card, a billing contact and an invoice table.",
        "harbour", "jakarta", SPLIT, body, ["home", "link", "chart", "settings", "users", "card", "shield", "download"], ["trustworthy", "plain", "light"], ["saas", "subscriptions", "billing", "membership"], "balanced",
        uses="showing what someone pays for and how much they have used: plan, limits, payment method, invoices",
        tags=["settings", "billing", "usage meters", "table", "side navigation"],
    )


def roles() -> Screen:
    perms = ["View projects", "Edit projects", "Manage members", "Export data", "Change billing", "Delete workspace"]
    roles = [("Owner", [1, 1, 1, 1, 1, 1]), ("Admin", [1, 1, 1, 1, 0, 0]), ("Editor", [1, 1, 0, 1, 0, 0]), ("Viewer", [1, 0, 0, 0, 0, 0])]
    head = "".join(f'<th style="text-align:center">{r}</th>' for r, _ in roles)
    rows = "".join(
        f'<tr><td><b>{p}</b></td>' + "".join(f'<td style="text-align:center"><label class="check"><input type="checkbox"{" checked" if values[i] else ""}{" disabled" if r == "Owner" else ""} aria-label="{r} can {p.lower()}"></label></td>' for r, values in roles) + "</tr>"
        for i, p in enumerate(perms)
    )
    members = [("Tobias Ortiz", "Owner", "TO"), ("Mara Chen", "Admin", "MC"), ("Eli Brandt", "Editor", "EB"), ("Joon Park", "Viewer", "JP")]
    lis = "".join(f'<li><span class="avatar">{i}</span><div style="flex:1"><b>{n}</b></div><select class="select" style="width:130px" aria-label="Role for {n}"><option{" selected" if r == "Owner" else ""}>Owner</option><option{" selected" if r == "Admin" else ""}>Admin</option><option{" selected" if r == "Editor" else ""}>Editor</option><option{" selected" if r == "Viewer" else ""}>Viewer</option></select></li>' for n, r, i in members)
    body = f"""
<div class="app">
{sidebar("Palisade", "P", [("home", "Overview", ""), ("layers", "Projects", ""), ("users", "Members", ""), ("shield", "Access", ""), ("settings", "Settings", "")], "Access", None, ("TO", "Tobias Ortiz", "Owner"))}
<main class="main">
  <div class="top"><div><h1>Roles and access</h1><p class="sub">Who can do what in this workspace.</p></div><button class="btn btn--primary">{icon("plus")}New role</button></div>
  <div class="grid" style="grid-template-columns:minmax(0,3fr) minmax(0,2fr)" id="split">
    <section aria-labelledby="pm"><div class="card-head"><h2 id="pm">Permissions</h2><span class="muted" style="font-size:.88rem">The Owner role cannot be changed</span></div><div class="table-wrap"><table><thead><tr><th>Permission</th>{head}</tr></thead><tbody>{rows}</tbody></table></div></section>
    <section class="card" aria-labelledby="mb"><div class="card-head"><h2 id="mb">Members</h2><span class="muted">4 people</span></div><ul class="list">{lis}</ul><button class="btn btn--sm" style="margin-top:10px">{icon("plus")}Invite a member</button></section>
  </div>
</main></div>"""
    return Screen(
        "settings-roles", "Settings: roles and permissions grid", "A permission matrix of rights against roles with checkboxes (the owner column fixed), beside a member list where each person's role is a select.",
        "ink", "grotesk", SPLIT, body, ["home", "layers", "users", "shield", "settings", "plus"], ["technical", "precise", "dark"], ["admin", "security", "enterprise", "developer tools"], "dense",
        uses="access control: which role may do what; the grid is easier to audit than a list of toggles",
        tags=["settings", "permissions", "matrix", "checkboxes", "dark"],
    )


ALL = [account, notifications, billing, roles]
