"""Playwright check of the bakery site Forge built. Usage: python verify_bakery.py <app_dir> <python> <phase>"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_DIR, PYTHON, PHASE = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
PORT = 5056
SHOTS = Path(r"C:\Work\ForgeRuns\shots")
SHOTS.mkdir(exist_ok=True)
BASE = f"http://127.0.0.1:{PORT}"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def port_open() -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


for f in list(APP_DIR.glob("*.db")) + list(APP_DIR.glob("*.sqlite*")):
    f.unlink()
server = subprocess.Popen([PYTHON, "app.py"], cwd=APP_DIR, stdout=open(Path(r'C:\Work\ForgeRuns') / (Path(sys.argv[1]).parent.name + '_server.log'), 'w'), stderr=subprocess.STDOUT, text=True)
try:
    deadline = time.time() + 40
    while time.time() < deadline and not port_open():
        if server.poll() is not None:
            break
        time.sleep(0.5)
    check("app starts on port 5056", port_open(), (Path(r'C:\Work\ForgeRuns') / (Path(sys.argv[1]).parent.name + '_server.log')).read_text()[-400:] if server.poll() is not None else "")
    if not port_open():
        raise SystemExit(1)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1200, "height": 800})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
        page.goto(BASE + "/")
        page.screenshot(path=str(SHOTS / "bakery_home.png"))
        check("home has the bakery name as the main heading", page.locator("h1").count() >= 1 and "Golden Crust" in page.locator("h1").first.inner_text())
        text = page.inner_text("body")
        check("home shows the tagline and opening hours", "Fresh bread, baked at dawn" in text and "7:00" in text, text[:200])
        for label in ("Home", "Menu", "Reservations", "Contact"):
            check(f"nav link {label}", page.locator("nav").get_by_role("link", name=label).count() >= 1)
        for tag in ("header", "nav", "main", "footer"):
            check(f"semantic <{tag}> present", page.locator(tag).count() >= 1)

        page.goto(BASE + "/menu")
        page.screenshot(path=str(SHOTS / "bakery_menu.png"))
        text = page.inner_text("body")
        check("menu shows rupee prices", text.count("₹") >= 8, f"count={text.count('₹')}")
        for cat in ("All", "Bread", "Pastries", "Cakes"):
            check(f"filter button {cat}", page.get_by_role("button", name=cat, exact=True).count() >= 1)
        url_before = page.url
        page.get_by_role("button", name="Cakes", exact=True).click()
        page.wait_for_timeout(400)
        visible_cakes = page.inner_text("body")
        check("filter works without reloading", page.url == url_before)
        bread_hidden = page.locator("text=/baguette|sourdough|loaf|bread roll|focaccia/i").first
        check("selecting Cakes hides the bread items", (not bread_hidden.is_visible()) if bread_hidden.count() else True, visible_cakes[:200])
        page.get_by_role("button", name="All", exact=True).click()
        page.wait_for_timeout(400)
        check("All shows the items again", page.inner_text("body").count("₹") >= 8)

        page.goto(BASE + "/reservations")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        def fill_and_book(name: str, phone: str, day: str, guests: str) -> str:
            page.goto(BASE + "/reservations")
            page.get_by_label("Name").fill(name)
            page.get_by_label("Phone").fill(phone)
            page.get_by_label("Date").fill(day)
            page.get_by_label("Time").fill("18:30")
            page.get_by_label("Guests").fill(guests)
            page.get_by_role("button", name="Book table").click()
            page.wait_for_timeout(700)
            return page.inner_text("body")

        text = fill_and_book("", "", tomorrow, "2")
        check("empty name/phone are rejected with a message", re.search(r"required|enter|must|missing|please", text, re.I) is not None, text[:250])
        text = fill_and_book("Asha", "9876543210", yesterday, "2")
        check("a past date is rejected", re.search(r"past|earlier|before today|future|valid date", text, re.I) is not None, text[:250])
        text = fill_and_book("Asha", "9876543210", tomorrow, "20")
        check("more than 12 guests is rejected", re.search(r"12|guests|between|at most|too many", text, re.I) is not None and "GC-" not in text, text[:250])
        text = fill_and_book("Asha", "9876543210", tomorrow, "4")
        check("a valid booking shows a GC- reference", re.search(r"GC-\d{4}", text) is not None, text[:250])
        page.screenshot(path=str(SHOTS / "bakery_booked.png"))
        text = fill_and_book("Dev", "9123456780", tomorrow, "2")
        check("the next booking gets the next reference", "GC-0002" in text, text[:250])

        page.goto(BASE + "/contact")
        text = page.inner_text("body")
        check("contact shows address, phone and email", re.search(r"@", text) and re.search(r"\d{5}", text) and re.search(r"address|street|road|lane", text, re.I), text[:250])

        # dark mode persists across pages and reloads
        page.goto(BASE + "/")
        before = page.evaluate("getComputedStyle(document.body).backgroundColor")
        page.get_by_role("button", name="Toggle dark mode").click()
        page.wait_for_timeout(300)
        after = page.evaluate("getComputedStyle(document.body).backgroundColor")
        check("dark mode changes the background", before != after, f"{before} -> {after}")
        page.screenshot(path=str(SHOTS / "bakery_dark.png"))
        page.goto(BASE + "/menu")
        persisted = page.evaluate("getComputedStyle(document.body).backgroundColor")
        check("dark mode persists on another page", persisted == after, f"{persisted} vs {after}")
        page.reload()
        check("dark mode persists after a reload", page.evaluate("getComputedStyle(document.body).backgroundColor") == after)

        # phone layout
        mobile = browser.new_context(viewport={"width": 375, "height": 700}).new_page()
        mobile.goto(BASE + "/")
        overflow = mobile.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        check("no horizontal scrolling at 375px", not overflow)
        toggle = mobile.get_by_role("button", name="Menu toggle")
        check("a 'Menu toggle' button exists on a phone", toggle.count() >= 1 and toggle.first.is_visible())
        link_hidden = not mobile.locator("nav").get_by_role("link", name="Reservations").first.is_visible()
        check("nav links are collapsed on a phone", link_hidden)
        if toggle.count():
            toggle.first.click()
            mobile.wait_for_timeout(300)
            check("the toggle reveals the links", mobile.locator("nav").get_by_role("link", name="Reservations").first.is_visible())
        mobile.screenshot(path=str(SHOTS / "bakery_mobile.png"))
        if PHASE >= 2:  # enhancement 1: cart and ordering
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/menu")
            adds = page.get_by_role("button", name="Add to cart")
            check("every menu item has an Add to cart button", adds.count() >= 8, str(adds.count()))
            adds.nth(0).click()
            adds.nth(1).click()
            page.wait_for_timeout(300)
            check("nav shows the cart count", re.search(r"cart\s*\(?\s*2", page.locator("nav").inner_text(), re.I) is not None, page.locator("nav").inner_text())
            page.goto(BASE + "/cart")
            page.screenshot(path=str(SHOTS / "bakery_cart.png"))
            text = page.inner_text("body")
            check("cart survives navigation and shows a total in rupees", "₹" in text and re.search(r"total", text, re.I) is not None, text[:250])
            qty = page.get_by_label("Quantity")
            total_before = re.search(r"Total:\s*₹\s*([0-9][0-9,.]*)", page.inner_text("body"))
            check("cart lists two lines with quantity fields", qty.count() == 2, str(qty.count()))
            if qty.count():
                qty.first.fill("3")
                qty.first.dispatch_event("change")
                page.wait_for_timeout(400)
                total_after = re.search(r"Total:\s*₹\s*([0-9][0-9,.]*)", page.inner_text("body"))
                check("changing a quantity updates the total", bool(total_before and total_after and total_before.group(1) != total_after.group(1)), f"{total_before and total_before.group(1)} -> {total_after and total_after.group(1)}")
            page2 = ctx.new_page()
            page2.goto(BASE + "/menu")
            page2.get_by_role("button", name="Add to cart").first.click()
            page2.goto(BASE + "/cart")
            before_text = page2.inner_text("main")
            page2.get_by_role("button", name="Place order").click()
            page2.wait_for_timeout(1000)
            after_text = page2.inner_text("main")
            check("an order without a name is refused with a visible message", after_text != before_text and "ORD-" not in after_text, after_text[:200])
            page2.close()
            page.get_by_label("Your name").fill("Asha")
            page.get_by_role("button", name="Place order").click()
            page.wait_for_timeout(700)
            text = page.inner_text("body")
            check("placing an order shows an ORD- reference", re.search(r"ORD-\d{4}", text) is not None, text[:250])
            page.goto(BASE + "/menu")
            check("the cart is empty after ordering", re.search(r"cart\s*\(?\s*0", page.locator("nav").inner_text(), re.I) is not None or "2" not in page.locator("nav").inner_text(), page.locator("nav").inner_text())
            page.goto(BASE + "/cart")
            page.get_by_label("Your name").fill("Nobody") if page.get_by_label("Your name").count() else None
            if page.get_by_role("button", name="Place order").count():
                page.get_by_role("button", name="Place order").click()
                page.wait_for_timeout(500)
                check("ordering with an empty cart is refused", re.search(r"empty|nothing|add|no items", page.inner_text("body"), re.I) is not None and "ORD-0002" not in page.inner_text("body"), page.inner_text("body")[:200])
            page.goto(BASE + "/admin/orders")
            text = page.inner_text("body")
            check("admin orders page lists the order", "ORD-0001" in text and "Asha" in text and "₹" in text, text[:300])
            page.screenshot(path=str(SHOTS / "bakery_orders.png"))
        if PHASE >= 3:  # enhancement 2: capacity and cancellation
            def book(name: str, guests: str) -> str:
                page.goto(BASE + "/reservations")
                page.get_by_label("Name").fill(name)
                page.get_by_label("Phone").fill("9000000000")
                page.get_by_label("Date").fill((date.today() + timedelta(days=5)).isoformat())
                page.get_by_label("Time").fill("12:00")
                page.get_by_label("Guests").fill(guests)
                page.get_by_role("button", name="Book table").click()
                page.wait_for_timeout(600)
                return page.inner_text("body")

            book("Group1", "12")
            text = book("Group2", "8")
            check("a booking filling the slot to exactly 20 is accepted", re.search(r"GC-\d{4}", text) is not None, text[:200])
            text = book("Group3", "1")
            check("the 21st seat is refused as fully booked", "fully booked" in text.lower() and "GC-" not in text, text[:250])
            page.goto(BASE + "/admin/reservations")
            page.screenshot(path=str(SHOTS / "bakery_admin_reservations.png"))
            text = page.inner_text("body")
            check("admin lists reservations", "Group1" in text and "Group2" in text and "Group3" not in text, text[:300])
            row = page.locator("tr", has_text="Group1")
            row.get_by_role("button", name="Cancel").click()
            page.wait_for_timeout(600)
            row = page.locator("tr", has_text="Group1")
            check("cancelling shows Cancelled and removes the button", "Cancelled" in row.inner_text() and row.get_by_role("button", name="Cancel").count() == 0, row.inner_text())
            text = book("Group4", "12")
            check("cancelled seats are free again", re.search(r"GC-\d{4}", text) is not None, text[:250])
        if PHASE >= 4:  # enhancement 3: English / Hindi switch
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/")
            check("English is the default (html lang=en)", page.evaluate("document.documentElement.lang") == "en")
            page.get_by_role("button", name="हिन्दी").click()
            page.wait_for_timeout(400)
            text = page.inner_text("body")
            check("home tagline switches to Hindi", "सुबह की ताज़ी रोटी" in text, text[:200])
            navtext = page.locator("nav").inner_text()
            check("navigation switches to Hindi", all(w in navtext for w in ("होम", "मेन्यू", "आरक्षण", "संपर्क")), navtext)
            check("html lang follows (hi)", page.evaluate("document.documentElement.lang") == "hi")
            check("the switch now offers English", page.get_by_role("button", name="English").count() >= 1)
            page.screenshot(path=str(SHOTS / "bakery_hindi.png"))
            page.goto(BASE + "/menu")
            check("Hindi persists on another page", page.get_by_role("button", name="सभी", exact=True).count() >= 1, page.inner_text("body")[:200])
            page.get_by_role("button", name="केक", exact=True).click()
            page.wait_for_timeout(400)
            bread = page.locator("text=/baguette|sourdough|loaf|bread roll|focaccia/i").first
            check("the filter works in Hindi", (not bread.is_visible()) if bread.count() else True)
            page.goto(BASE + "/reservations")
            check("the booking button is translated", page.get_by_role("button", name="टेबल बुक करें").count() >= 1)
            page.reload()
            check("Hindi persists after a reload", page.evaluate("document.documentElement.lang") == "hi")
            page.get_by_role("button", name="English").click()
            page.wait_for_timeout(400)
            check("switching back restores English", "Reservations" in page.locator("nav").inner_text() and page.evaluate("document.documentElement.lang") == "en")
        check("no console or JavaScript errors", not errors, "; ".join(errors)[:300])
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
