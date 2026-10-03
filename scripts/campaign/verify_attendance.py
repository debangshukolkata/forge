"""Playwright check of the attendance app Forge built. Usage: python verify_attendance.py <app_dir> <python> <phase>
phase 1 = the original requirement; later phases add the checks for each enhancement."""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_DIR, PYTHON, PHASE = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
SHOTS = Path(r"C:\Work\ForgeRuns\shots")
SHOTS.mkdir(exist_ok=True)
BASE = "http://127.0.0.1:5055"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def port_open() -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", 5055)) == 0


def body(page) -> str:  # type: ignore[no-untyped-def]
    return page.inner_text("body")


db = list(APP_DIR.glob("*.db")) + list(APP_DIR.glob("*.sqlite*"))
for f in db:  # a clean database each run so the seed data is what the check expects
    f.unlink()
server = subprocess.Popen([PYTHON, "app.py"], cwd=APP_DIR, stdout=open(Path(r'C:\Work\ForgeRuns') / (Path(sys.argv[1]).parent.name + '_server.log'), 'w'), stderr=subprocess.STDOUT, text=True)
try:
    deadline = time.time() + 40
    while time.time() < deadline and not port_open():
        if server.poll() is not None:
            break
        time.sleep(0.5)
    check("app starts on port 5055", port_open(), (Path(r'C:\Work\ForgeRuns') / (Path(sys.argv[1]).parent.name + '_server.log')).read_text()[-400:] if server.poll() is not None else "")
    if not port_open():
        raise SystemExit(1)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/")
        page.screenshot(path=str(SHOTS / "attendance_home.png"))
        options = [o.inner_text() for o in page.locator("select option").all()]
        check("dropdown lists the seeded employees", all(n in " ".join(options) for n in ("Ravi", "Meena", "Arjun")), str(options))
        page.select_option("select", label=next((o for o in options if "Ravi" in o), "Ravi"))
        page.get_by_role("button", name="Check in").click()
        page.wait_for_timeout(600)
        text = body(page)
        check("check in shows a confirmation", re.search(r"checked in", text, re.I) is not None, text[:200])
        page.screenshot(path=str(SHOTS / "attendance_checked_in.png"))
        page.select_option("select", label=next((o for o in options if "Ravi" in o), "Ravi"))
        page.get_by_role("button", name="Check in").click()
        page.wait_for_timeout(600)
        text = body(page)
        check("a second check in is refused", re.search(r"already|error|cannot|can't|not allowed|must", text, re.I) is not None, text[:200])
        page.select_option("select", label=next((o for o in options if "Ravi" in o), "Ravi"))
        page.get_by_role("button", name="Check out").click()
        page.wait_for_timeout(600)
        text = body(page)
        check("check out shows a confirmation", re.search(r"checked out", text, re.I) is not None, text[:200])
        page.select_option("select", label=next((o for o in options if "Ravi" in o), "Ravi"))
        page.get_by_role("button", name="Check out").click()
        page.wait_for_timeout(600)
        text = body(page)
        check("a second check out is refused", re.search(r"already|error|cannot|can't|not allowed|must|not checked in|no open", text, re.I) is not None, text[:200])
        # checking out someone who never checked in
        page.select_option("select", label=next((o for o in options if "Arjun" in o), "Arjun"))
        page.get_by_role("button", name="Check out").click()
        page.wait_for_timeout(600)
        text = body(page)
        check("check out without a check in is refused", re.search(r"not checked in|no check|first|error|cannot|can't|must|no open", text, re.I) is not None, text[:200])

        page.goto(BASE + "/employees")
        page.get_by_label("Name").fill("Kiran")
        page.get_by_label("Department").fill("Support")
        page.get_by_role("button", name="Add employee").click()
        page.wait_for_timeout(600)
        text = body(page)
        check("a new employee appears in the table", "Kiran" in text and "Support" in text, text[:300])
        page.screenshot(path=str(SHOTS / "attendance_employees.png"))

        page.goto(BASE + "/hr")
        text = body(page)
        check("HR page has a date picker", page.locator("input[type=date]").count() >= 1)
        check("HR page lists Ravi's record with the columns", "Ravi" in text and "Hours" in text and "Engineering" in text, text[:300])
        page.screenshot(path=str(SHOTS / "attendance_hr.png"))
        if PHASE >= 2:  # enhancement 1: leave requests
            def request_leave(who: str, start: str, end: str, reason: str) -> str:
                page.goto(BASE + "/leave")
                page.select_option("select", label=next((o.inner_text() for o in page.locator("select option").all() if who in o.inner_text()), who))
                page.get_by_label("Start date").fill(start)
                page.get_by_label("End date").fill(end)
                page.get_by_label("Reason").fill(reason)
                page.get_by_role("button", name="Request leave").click()
                page.wait_for_timeout(600)
                return body(page)

            text = request_leave("Meena", "2026-11-02", "2026-11-04", "Family event")
            check("leave request is confirmed", re.search(r"request|submitted|saved|pending|thank", text, re.I) is not None, text[:200])
            text = request_leave("Arjun", "2026-11-10", "2026-11-05", "Backwards dates")
            check("an end date before the start date is refused", re.search(r"before|invalid|error|earlier|must|cannot|can't", text, re.I) is not None, text[:200])
            request_leave("Arjun", "2026-12-01", "2026-12-02", "Conference")
            page.goto(BASE + "/hr/leaves")
            text = body(page)
            check("HR leaves page lists the requests as Pending", "Meena" in text and "Family event" in text and "Pending" in text, text[:300])
            page.screenshot(path=str(SHOTS / "attendance_leaves.png"))
            row = page.locator("tr", has_text="Family event")
            row.get_by_role("button", name="Approve").click()
            page.wait_for_timeout(600)
            row = page.locator("tr", has_text="Family event")
            check("approving shows Approved and removes the buttons", "Approved" in row.inner_text() and row.get_by_role("button", name="Approve").count() == 0, row.inner_text())
            row = page.locator("tr", has_text="Conference")
            row.get_by_role("button", name="Reject").click()
            page.wait_for_timeout(600)
            row = page.locator("tr", has_text="Conference")
            check("rejecting shows Rejected", "Rejected" in row.inner_text(), row.inner_text())
            page.goto(BASE + "/hr")
            check("the HR page links to the leaves page", page.locator("a[href*='leaves']").count() >= 1)
        if PHASE >= 3:  # enhancement 2: department filter + CSV export on /hr
            page.goto(BASE + "/")
            page.select_option("select", label=next((o.inner_text() for o in page.locator("select option").all() if "Meena" in o.inner_text()), "Meena"))
            page.get_by_role("button", name="Check in").click()
            page.wait_for_timeout(600)
            page.goto(BASE + "/hr")
            try:
                page.get_by_label("Department").select_option(label="HR")
                page.get_by_role("button", name="Show").click()
                page.wait_for_timeout(600)
                text = body(page)
                check("department filter shows only that department", "Meena" in text and "Ravi" not in text, text[:300])
                page.screenshot(path=str(SHOTS / "attendance_hr_filtered.png"))
            except Exception as error:  # noqa: BLE001
                check("department filter works", False, str(error)[:200])
            try:
                page.get_by_label("Department").select_option(label="All")
                page.get_by_role("button", name="Show").click()
                page.wait_for_timeout(600)
                with page.expect_download(timeout=10000) as info:
                    page.get_by_role("link", name="Export CSV").click()
                download = info.value
                csv_text = Path(download.path()).read_text(encoding="utf-8-sig")
                lines = [l for l in csv_text.splitlines() if l.strip()]
                check("CSV has the header row", lines and [c.strip() for c in lines[0].split(",")] == ["Employee", "Department", "Check in", "Check out", "Hours worked"], lines[0] if lines else "")
                check("CSV lists both employees", "Ravi" in csv_text and "Meena" in csv_text, csv_text[:300])
                check("CSV file name carries the date", re.search(r"attendance.*\d{4}-\d{2}-\d{2}.*\.csv", download.suggested_filename) is not None, download.suggested_filename)
            except Exception as error:  # noqa: BLE001
                check("CSV export works", False, str(error)[:200])
        if PHASE >= 4:  # enhancement 3: navigation bar + monthly report with an inline SVG chart
            for path in ("/", "/employees", "/hr", "/leave", "/hr/leaves", "/report"):
                page.goto(BASE + path)
                nav = page.locator("nav")
                links = [a.inner_text().strip() for a in nav.locator("a").all()] if nav.count() else []
                check(f"nav bar on {path} links to every page", nav.count() >= 1 and all(any(w.lower() in l.lower() for l in links) for w in ("check", "employees", "hr", "leave", "report")), str(links))
            page.goto(BASE + "/report")
            page.screenshot(path=str(SHOTS / "attendance_report.png"))
            text = body(page)
            check("report has a month picker", page.locator("input[type=month]").count() >= 1)
            check("report table shows days present and total hours per employee", "Ravi" in text and "Days present" in text and "Total hours" in text, text[:300])
            check("report draws an inline SVG bar chart", page.locator("svg").count() >= 1 and page.locator("svg rect").count() >= 3, f"svg={page.locator('svg').count()} rect={page.locator('svg rect').count()}")
            ext = page.evaluate("Array.from(document.querySelectorAll('script[src],link[href]')).map(e => e.src || e.href).filter(u => !u.startsWith(location.origin))")
            check("no external CDN scripts or styles", not ext, str(ext))
            page.fill("input[type=month]", "2025-01")
            page.get_by_role("button", name="Show").click()
            page.wait_for_timeout(600)
            text = body(page)
            check("a month with no records shows zero days present", re.search(r"no (records|attendance)|0", text, re.I) is not None, text[:200])
        if PHASE >= 5:  # enhancement 4: settings + late marking
            page.goto(BASE + "/settings")
            check("settings default to 09:30 and 10 grace minutes", page.get_by_label("Work start time").input_value()[:5] == "09:30" and page.get_by_label("Grace minutes").input_value() == "10", page.get_by_label("Work start time").input_value())
            page.get_by_label("Work start time").fill("00:00")
            page.get_by_label("Grace minutes").fill("0")
            page.get_by_role("button", name="Save settings").click()
            page.wait_for_timeout(600)
            check("saving shows a confirmation", "Settings saved" in body(page), body(page)[:200])
            page.goto(BASE + "/hr")
            text = body(page)
            check("with a 00:00 start, today's check-ins are marked Late", "Late" in text and re.search(r"Late today:\s*[1-9]", text) is not None, text[:300])
            page.screenshot(path=str(SHOTS / "attendance_late.png"))
            page.goto(BASE + "/settings")
            page.get_by_label("Work start time").fill("23:59")
            page.get_by_label("Grace minutes").fill("0")
            page.get_by_role("button", name="Save settings").click()
            page.wait_for_timeout(600)
            page.goto(BASE + "/hr")
            text = body(page)
            check("with a 23:59 start, nobody is Late", re.search(r"Late today:\s*0", text) is not None and not re.search(r"\bLate\b(?!\s*today)", text), text[:300])
            page.goto(BASE + "/settings")
            page.get_by_label("Grace minutes").fill("-5")
            page.get_by_role("button", name="Save settings").click()
            page.wait_for_timeout(600)
            check("a negative grace value is rejected", "Settings saved" not in body(page) and re.search(r"negative|invalid|error|must|cannot|can't|at least", body(page), re.I) is not None, body(page)[:200])
        if PHASE >= 6:  # enhancement 5: employee detail page with a monthly calendar
            import calendar as _cal
            page.goto(BASE + "/employees")
            row = page.locator("tr", has_text="Ravi")
            row.get_by_role("link", name="View").first.click()
            page.wait_for_timeout(600)
            text = body(page)
            heading = page.locator("h1").first.inner_text() if page.locator("h1").count() else text[:80]
            check("detail page heading has the name and department", "Ravi" in heading and "Engineering" in heading, heading)
            check("detail page has a month picker and Show button", page.locator("input[type=month]").count() >= 1 and page.get_by_role("button", name="Show").count() >= 1)
            check("weekday header Mon..Sun", all(d in text for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")), text[:300])
            today = __import__("datetime").date.today()
            days = _cal.monthrange(today.year, today.month)[1]
            present = page.locator(".present")
            check("today is shaded as present with the check-in details", present.count() == 1 and re.search(r"%d" % today.day, present.first.inner_text()) is not None, f"present={present.count()}")
            check("today's cell has the class today", page.locator(".today").count() == 1)
            weekends = sum(1 for d in range(1, days + 1) if __import__("datetime").date(today.year, today.month, d).weekday() >= 5)
            check("weekend cells carry the class weekend", page.locator(".weekend").count() >= weekends, f"{page.locator('.weekend').count()} vs {weekends}")
            check("summary shows days present and total hours", re.search(r"Days present:\s*1", text) is not None and re.search(r"Total hours:", text) is not None, text[:300])
            page.screenshot(path=str(SHOTS / "attendance_calendar.png"))
            page.fill("input[type=month]", "2025-01")
            page.get_by_role("button", name="Show").click()
            page.wait_for_timeout(600)
            text = body(page)
            check("an empty month shows 0 days present and no shaded cells", re.search(r"Days present:\s*0", text) is not None and page.locator(".present").count() == 0, text[:200])
            mobile = browser.new_page(viewport={"width": 375, "height": 700})
            mobile.goto(page.url.split("?")[0])
            check("calendar page does not scroll horizontally at 375px", not mobile.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"))
            mobile.screenshot(path=str(SHOTS / "attendance_calendar_mobile.png"))
        if PHASE >= 7:  # enhancement 6: dark mode
            def bg() -> str:
                return page.evaluate("getComputedStyle(document.body).backgroundColor")

            def fg() -> str:
                return page.evaluate("getComputedStyle(document.body).color")

            page.goto(BASE + "/")
            light_bg, light_fg = bg(), fg()
            for path in ("/", "/employees", "/hr", "/leave", "/hr/leaves", "/report", "/settings"):
                page.goto(BASE + path)
                check(f"dark mode button on {path}", page.get_by_role("button", name="Toggle dark mode").count() >= 1)
            page.goto(BASE + "/")
            page.get_by_role("button", name="Toggle dark mode").click()
            page.wait_for_timeout(300)
            dark_bg, dark_fg = bg(), fg()
            check("toggling changes background and text colour", dark_bg != light_bg and dark_fg != light_fg, f"{light_bg}/{light_fg} -> {dark_bg}/{dark_fg}")
            def lum(c: str) -> float:
                nums = [int(x) for x in re.findall(r"\d+", c)[:3]]
                return sum(n * w for n, w in zip(nums, (0.2126, 0.7152, 0.0722))) / 255
            check("dark theme: background darker than text", lum(dark_bg) < lum(dark_fg), f"{dark_bg} vs {dark_fg}")
            for path in ("/employees", "/hr", "/report", "/settings"):
                page.goto(BASE + path)
                check(f"dark mode persists on {path}", bg() == dark_bg, f"{bg()} vs {dark_bg}")
            page.goto(BASE + "/hr")
            page.screenshot(path=str(SHOTS / "attendance_dark_hr.png"))
            page.reload()
            check("dark mode persists after a reload", bg() == dark_bg)
            page.goto(BASE + "/employees")
            page.get_by_role("link", name="View").first.click()
            page.wait_for_timeout(500)
            cell = page.locator(".present").first
            if cell.count():
                cbg = cell.evaluate("e => getComputedStyle(e).backgroundColor"); cfg = cell.evaluate("e => getComputedStyle(e).color")
                check("a shaded present day stays readable in dark mode", abs(lum(cbg) - lum(cfg)) > 0.3, f"{cbg} / {cfg}")
            page.screenshot(path=str(SHOTS / "attendance_dark_calendar.png"))
            tbl = page.locator("th").first
            if tbl.count():
                tb = tbl.evaluate("e => getComputedStyle(e).backgroundColor"); tf = tbl.evaluate("e => getComputedStyle(e).color")
                check("table headers stay readable in dark mode", abs(lum(tb) - lum(tf)) > 0.3 or tb == "rgba(0, 0, 0, 0)", f"{tb} / {tf}")
            page.get_by_role("button", name="Toggle dark mode").click()
            page.wait_for_timeout(300)
            check("toggling again restores the light theme", bg() == light_bg, f"{bg()} vs {light_bg}")
        check("no JavaScript errors", not errors, "; ".join(errors))
        browser.close()
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
