"""The Dependencies tab in headless Edge (D-238): the list comes from the project's own files, the check asks
before anything is sent, and each vulnerability shows which source reported it. Both vulnerability sources
are replaced by canned answers here (test_deps.py and a live run cover the real ones)."""

from __future__ import annotations

import pytest

from forge.deps import audit, osv
from forge.deps.model import Dependency, Finding, SourceStatus
from forge.safety.server_security import ServerSecurity
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import configured_secrets, server, workspace  # noqa: F401  (fixtures)

playwright_api = pytest.importorskip("playwright.sync_api")


def _finding(dependency: Dependency, source: str, vuln_id: str, severity: str) -> Finding:
    return Finding(
        id=vuln_id,
        aliases=["CVE-2024-0001"],
        package=dependency.name,
        ecosystem=dependency.ecosystem,
        version=str(dependency.version),
        summary="Remote code execution in the parser",
        severity=severity,  # type: ignore[arg-type]
        fixed_in=["9.9.9"],
        link=f"https://osv.dev/vulnerability/{vuln_id}",
        found_by=[source],
    )


def test_dependencies_tab_lists_checks_and_names_the_source(
    server: ServerSecurity,  # noqa: F811
    workspace: Workspace,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[list[str]] = []

    def fake_osv(dependencies: list[Dependency], client_factory: object = None):  # type: ignore[no-untyped-def]
        known = [d for d in dependencies if d.version]
        sent.append([f"{d.name}=={d.version}" for d in known])
        return [_finding(known[0], "osv.dev", "GHSA-test-0001", "high")], SourceStatus(
            name="osv.dev", status="ok", checked=len(known), found=1
        )

    def fake_audit(dependencies: list[Dependency], runner: object = None):  # type: ignore[no-untyped-def]
        known = [d for d in dependencies if d.version]
        return [_finding(known[0], "pip-audit", "PYSEC-test-0001", "unknown")], SourceStatus(
            name="pip-audit", status="ok", checked=len(known), found=1
        )

    monkeypatch.setattr(osv, "check", fake_osv)
    monkeypatch.setattr(audit, "check", fake_audit)
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        page.evaluate(
            "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'},"
            " body: JSON.stringify({workspace: p})})",
            str(workspace.root),
        )
        page.reload()
        page.click("[role=tab]:has-text('Deps')")
        page.wait_for_selector("[data-library]")  # the list needs no network and no click
        assert page.locator("[data-testid=deps-summary]").count() == 0
        assert sent == []  # nothing was sent anywhere yet

        page.click("button:has-text('Check for vulnerabilities')")
        dialog = page.locator("[role=alertdialog][aria-label='Check for vulnerabilities']")
        assert "name and version" in dialog.inner_text() and sent == []  # asked first, still nothing sent
        dialog.locator("button:has-text('Cancel')").click()
        assert sent == []
        page.click("button:has-text('Check for vulnerabilities')")
        dialog.locator("button:has-text('Check now')").click()

        summary = page.locator("[data-testid=deps-summary]")
        summary.wait_for()
        assert "osv.dev" in summary.inner_text() and "pip-audit" in summary.inner_text()
        assert sent and len(sent[0]) > 0 and "==" in sent[0][0]  # only names and versions
        assert (
            page.locator("[data-library]").first.get_attribute("data-vulnerable") is not None
        )  # worst first
        row = page.locator("[data-vulnerable]").first
        row.locator("button").click()
        finding = page.locator("[data-finding]").first
        text = finding.inner_text()
        assert "Remote code execution" in text and "Fixed in: 9.9.9" in text
        assert "osv.dev" in text and "pip-audit" in text  # found by both sources
        page.screenshot(path=str(shots / "dependencies-light.png"))

        page.reload()  # the last check is remembered with the project
        page.click("[role=tab]:has-text('Deps')")
        page.locator("[data-testid=deps-summary]").wait_for()
        browser.close()
    assert not problems, problems
