"""D-366: the application-screen recipes (dashboards, tables, forms, settings, web-app screens) are standalone, render cleanly at desktop and phone
width, are in the catalogue with pictures, and are found by the product the model is building."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from forge.parity.assets import build_catalogue, search
from forge.tools.ui_audit import AUDIT_SCRIPT

SKILL = Path(__file__).resolve().parent.parent / "src" / "forge" / "skills" / "ui-design-quality"
FILES = sorted((SKILL / "recipes" / "app-screens").glob("*.html"))
FAMILIES = {"dashboard": 4, "table": 4, "form": 5, "settings": 4}


def test_there_are_screens_in_every_family_each_in_the_catalogue_with_pictures() -> None:
    assert (
        len(FILES) == 40
    )  # 24 general screens, ten back-office ones (D-487), four patterns (D-491), two list patterns (D-495)
    for family, count in FAMILIES.items():
        assert len([f for f in FILES if f.stem.startswith(family + "-")]) == count, family
    ids = {
        a.id
        for a in build_catalogue(SKILL).assets
        if a.id.startswith("app-") and not a.id.startswith("app-react-")
    }
    assert ids == {f"app-{f.stem}" for f in FILES}
    for file in FILES:
        for label in ("desktop", "phone"):
            assert (SKILL / "assets" / "preview" / f"app-{file.stem}-{label}.jpg").is_file(), (
                file.stem,
                label,
            )


def test_a_screen_is_standalone_and_uses_only_token_variables_for_colour() -> None:
    for file in FILES:
        text = file.read_text(encoding="utf-8")
        assert "<h1" in text and "<title>" in text and 'lang="en"' in text, file.stem
        assert "http://" not in text.replace("http://www.w3.org", "") and "https://" not in text, (
            f"{file.stem} must not load anything"
        )
        body = text.split("</style>", 1)[1]
        assert "#" not in "".join(part.split('"')[0] for part in body.split("color:#")[1:]), (
            file.stem
        )  # no hard-coded colours in the markup


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(str(error))
        yield launched
        launched.close()


@pytest.mark.parametrize("file", FILES, ids=[f.stem for f in FILES])
def test_a_screen_has_no_sideways_scroll_and_a_clean_audit_at_both_widths(
    file: Path, browser: object
) -> None:
    for width in (1280, 375):
        page = browser.new_page(viewport={"width": width, "height": 800})  # type: ignore[attr-defined]
        page.goto(file.resolve().as_uri())
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1, (
            f"{file.stem} scrolls sideways at {width}"
        )
        if width == 1280:
            findings = [
                f for f in page.evaluate(AUDIT_SCRIPT)["findings"] if "system font stack" not in f
            ]  # the recipes name their fonts; fetch_font brings them in
            assert findings == [], (file.stem, findings)
        page.close()


RETRIEVAL = [
    ("sales revenue dashboard with kpi cards and chart", "app-dashboard-kpi"),
    ("logistics operations board with shipments and delays", "app-dashboard-ops"),
    ("dark product analytics traffic funnel", "app-dashboard-analytics"),
    ("personal day view with goals and schedule", "app-dashboard-personal"),
    ("people table with filters and bulk actions", "app-table-data"),
    ("list and detail view for purchase order approvals", "app-table-master-detail"),
    ("kanban board with lanes and cards", "app-table-kanban"),
    ("inventory stock count grid for fast data entry", "app-table-editable-grid"),
    ("multi step onboarding wizard with billing form", "app-form-wizard"),
    ("invoice with line items and totals", "app-form-line-entry"),
    ("long registration form with validation errors", "app-form-long"),
    ("sign in page with split screen", "app-form-sign-in"),
    ("quick capture log entry form", "app-form-quick-capture"),
    ("account settings with api keys and security toggles", "app-settings-account"),
    ("notification preferences matrix with quiet hours", "app-settings-notifications"),
    ("plan usage and invoices billing page", "app-settings-billing"),
    ("roles and permissions grid", "app-settings-roles"),
    ("email inbox with three panes", "app-inbox"),
    ("team chat with conversations and composer", "app-chat"),
    ("week calendar with events", "app-calendar"),
    ("customer profile record page with timeline", "app-record"),
    ("store locator pickup points on a map", "app-map-list"),
    ("document editor with comments and outline", "app-editor"),
    ("empty state error offline and loading skeleton", "app-empty-states"),
    ("approval queue for expenses and purchase orders with a decision panel", "app-approval-queue"),
    ("audit log of who changed what with a before and after comparison", "app-audit-log"),
    ("order fulfilment pick pack and ship for a warehouse", "app-order-fulfilment"),
    ("stock levels with reorder alerts for a kitchen", "app-inventory-levels"),
    ("accounts receivable ageing with overdue invoices and reminders", "app-invoice-ageing"),
    ("customer support ticket queue with reply deadlines", "app-helpdesk-queue"),
    ("csv import with column mapping and validation errors", "app-csv-import"),
    ("report builder with filters, a chart and a scheduled email", "app-report-builder"),
    ("background jobs and queues monitor with a failed job to retry", "app-jobs-monitor"),
    ("resource scheduling timeline for rooms staff and vans with conflicts", "app-resource-timeline"),
    ("task list grouped by overdue and due this week with summary tiles", "app-grouped-tasks"),
    ("department hierarchy tree with a detail panel and notes", "app-hierarchy-detail"),
    ("project card grid with progress budget and status", "app-card-grid"),
    ("slide-over drawer form with collapsible sections", "app-drawer-form"),
    ("invoice list with status links bulk actions and row actions on hover", "app-list-bulk"),
    ("document collection with a switch between grid and table view", "app-collection-switch"),
]


def test_the_product_being_built_finds_its_screen() -> None:
    catalogue = [a for a in build_catalogue(SKILL).assets]
    missed = [
        (prompt, expected, [a.id for a in search(catalogue, prompt, limit=3)])
        for prompt, expected in RETRIEVAL
        if expected not in [a.id for a in search(catalogue, prompt, limit=3)]
    ]
    assert len(missed) <= 2, missed  # at least 90 percent, as for the other assets
