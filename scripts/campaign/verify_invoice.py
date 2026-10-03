"""Playwright check of the invoice extraction app Forge built. Usage: python verify_invoice.py <app_dir> <python> <phase>"""

from __future__ import annotations

import csv
import io
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_DIR, PYTHON, PHASE = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
PORT = 5057
INV = Path(r"C:\Work\ForgeRuns\invoices")
SHOTS = Path(r"C:\Work\ForgeRuns\shots")
SHOTS.mkdir(exist_ok=True)
BASE = f"http://127.0.0.1:{PORT}"
LOG = Path(r"C:\Work\ForgeRuns") / (APP_DIR.parent.name + "_server.log")
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
server = subprocess.Popen([PYTHON, "app.py"], cwd=APP_DIR, stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)
try:
    deadline = time.time() + 40
    while time.time() < deadline and not port_open():
        if server.poll() is not None:
            break
        time.sleep(0.5)
    check("app starts on port 5057", port_open(), LOG.read_text()[-400:] if server.poll() is not None else "")
    if not port_open():
        raise SystemExit(1)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def upload(files: list[str]) -> str:
            page.goto(BASE + "/")
            page.get_by_label("Invoice files").set_input_files([str(INV / f) for f in files])
            page.get_by_role("button", name="Extract").click()
            page.wait_for_timeout(1500)
            return page.inner_text("body")

        text = upload(["invoice_a.txt"])
        page.screenshot(path=str(SHOTS / "invoice_a.png"))
        check("A: vendor", "ACME SUPPLIES PVT LTD" in text, text[:300])
        check("A: invoice number", "INV-2024-0042" in text)
        check("A: date normalised", "2024-03-15" in text)
        check("A: total 3658", re.search(r"3658(\.00?)?", text.replace(",", "")) is not None and "310.0" not in text, text[:300])
        check("A: line items", "Copy paper" in text and "Stapler" in text)

        text = upload(["invoice_b.txt"])
        check("B: vendor", "Blue Ocean Logistics" in text, text[:300])
        check("B: invoice number", "BO/778" in text)
        check("B: date normalised", "2024-03-03" in text)
        check("B: total 20000 in INR", re.search(r"20000(\.00)?", text.replace(",", "")) is not None and "INR" in text, text[:300])

        text = upload(["invoice_c.txt"])
        check("C: vendor", "Northwind Traders" in text, text[:300])
        check("C: number and date", "2024/0099" in text and "2024-02-27" in text)
        check("C: total 1200.5 in USD", re.search(r"1200\.5(0)?\b", text.replace(",", "")) is not None and "USD" in text, text[:300])

        text = upload(["notes.txt"])
        check("a note is reported as not an invoice", "Not an invoice" in text, text[:300])

        text = upload(["invoice_a.pdf"])
        page.screenshot(path=str(SHOTS / "invoice_pdf.png"))
        check("PDF: same fields as the text version", "INV-2024-0042" in text and "2024-03-15" in text and "3658" in text.replace(",", ""), text[:300])

        text = upload(["invoice_a.txt", "invoice_b.txt", "invoice_c.txt", "notes.txt"])
        check("several files at once: all four shown", all(k in text for k in ("INV-2024-0042", "BO/778", "2024/0099", "Not an invoice")), text[:400])
        page.screenshot(path=str(SHOTS / "invoice_batch.png"))
        with page.expect_download(timeout=10000) as info:
            page.get_by_role("link", name="Download JSON").first.click()
        data = json.loads(Path(info.value.path()).read_text(encoding="utf-8"))
        check("Download JSON returns the extracted fields", isinstance(data, dict) and any("INV" in json.dumps(data) or "BO/" in json.dumps(data) or "2024/0099" in json.dumps(data) for _ in [0]), json.dumps(data)[:200])

        page.goto(BASE + "/history")
        text = page.inner_text("body")
        page.screenshot(path=str(SHOTS / "invoice_history.png"))
        check("history lists processed invoices", "ACME" in text and "Blue Ocean" in text and "Northwind" in text, text[:300])
        with page.expect_download(timeout=10000) as info:
            page.get_by_role("link", name="Export CSV").click()
        rows = list(csv.reader(io.StringIO(Path(info.value.path()).read_text(encoding="utf-8-sig"))))
        check("CSV header is exactly as specified", rows and rows[0] == ["File", "Vendor", "Invoice number", "Invoice date", "Currency", "Total", "Status"], str(rows[:1]))
        check("CSV has invoice rows", len(rows) >= 4, str(len(rows)))
        if PHASE >= 2:  # enhancement 1: duplicate detection + corrections
            page.goto(BASE + "/history")
            before = page.inner_text("body").count("ACME")
            text = upload(["invoice_a.txt"])
            check("re-uploading the same invoice is flagged as a duplicate", re.search(r"duplicate", text, re.I) is not None, text[:300])
            page.goto(BASE + "/history")
            check("a duplicate does not add a second history row", page.inner_text("body").count("ACME") == before, f"{before} -> {page.inner_text('body').count('ACME')}")
            row = page.locator("tr", has_text="Blue Ocean")
            row.get_by_role("link", name="Edit").first.click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(SHOTS / "invoice_edit.png"))
            try:
                page.get_by_label("Vendor").fill("Blue Ocean Logistics Pvt Ltd")
                page.get_by_label("Total").fill("21000")
                page.get_by_role("button", name="Save corrections").click()
                page.wait_for_timeout(700)
                page.goto(BASE + "/history")
                row = page.locator("tr", has_text="Blue Ocean")
                rt = row.inner_text()
                check("the corrected vendor and total show in history", "Pvt Ltd" in rt and "21000" in rt.replace(",", ""), rt)
                check("the corrected row is marked Corrected", "Corrected" in rt, rt)
                with page.expect_download(timeout=10000) as info:
                    page.get_by_role("link", name="Export CSV").click()
                csv_text = Path(info.value.path()).read_text(encoding="utf-8-sig")
                check("the CSV carries the corrections", "Pvt Ltd" in csv_text and "21000" in csv_text.replace(",", ""), csv_text[:300])
            except Exception as error:  # noqa: BLE001
                check("the correction form works", False, str(error)[:200])
        check("no JavaScript errors", not errors, "; ".join(errors)[:300])
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
