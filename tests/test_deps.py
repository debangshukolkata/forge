"""The Dependencies section (D-238): scanning manifests, the two vulnerability sources (at the transport
layer: no real network here), and the merge that records which source found what."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx

from forge.deps import audit, osv
from forge.deps.check import merge, run_check
from forge.deps.licenses import ClientFactory
from forge.deps.model import Dependency, Finding
from forge.deps.scan import installed_python_packages, scan_project


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _by_name(deps: list[Dependency]) -> dict[str, Dependency]:
    return {d.name: d for d in deps}


def test_requirements_pyproject_and_locks(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "requests==2.19.0\nflask>=2.0  # web\n-e .\n# note\n-r extra.txt\n")
    _write(tmp_path / "extra.txt", "pyyaml[extra]==6.0.1 ; python_version > '3.8'\n")
    _write(tmp_path / "requirements-dev.txt", "pytest>=8\n")
    _write(
        tmp_path / "pyproject.toml",
        '[project]\nname="x"\ndependencies=["httpx>=0.27"]\n'
        '[project.optional-dependencies]\ndev=["ruff"]\nweb=["fastapi"]\n',
    )
    _write(
        tmp_path / "poetry.lock",
        '[[package]]\nname = "flask"\nversion = "2.3.1"\n'
        '[[package]]\nname = "itsdangerous"\nversion = "2.1.2"\n',
    )
    found = _by_name(scan_project(tmp_path))
    assert found["requests"].version == "2.19.0" and found["requests"].direct
    assert (
        found["flask"].version == "2.3.1" and found["flask"].spec == ">=2.0"
    )  # a range takes the locked version
    assert found["pyyaml"].version == "6.0.1"
    assert found["pytest"].dev and found["ruff"].dev and not found["fastapi"].dev
    assert found["itsdangerous"].direct is False  # only in the lock file: pulled in by another library
    assert found["httpx"].version is None  # a range with no lock and nothing installed: unknown


def test_npm_manifest_and_lock_versions(tmp_path: Path) -> None:
    manifest = {"dependencies": {"lodash": "^4.17.0"}, "devDependencies": {"vite": "^5"}}
    _write(tmp_path / "package.json", json.dumps(manifest))
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {},
            "node_modules/lodash": {"version": "4.17.15"},
            "node_modules/vite": {"version": "5.0.1"},
            "node_modules/vite/node_modules/esbuild": {"version": "0.19.0"},
            "node_modules/@scope/pkg": {"version": "1.0.0"},
        },
    }
    _write(tmp_path / "package-lock.json", json.dumps(lock))
    found = _by_name(scan_project(tmp_path))
    assert found["lodash"].version == "4.17.15" and found["lodash"].ecosystem == "npm"
    assert found["vite"].dev and found["vite"].version == "5.0.1"
    assert found["@scope/pkg"].direct is False and found["esbuild"].version == "0.19.0"


def test_installed_packages_fill_unpinned_versions_and_skip_environments(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    (venv / "Lib" / "site-packages" / "typing_extensions-4.16.0.dist-info").mkdir(parents=True)
    (venv / "Lib" / "site-packages" / "httpx-0.28.1.dist-info").mkdir()
    _write(tmp_path / "app" / "requirements.txt", "httpx>=0.27\n")
    junk = {"dependencies": {"nope": "1"}}
    _write(tmp_path / "app" / "node_modules" / "junk" / "package.json", json.dumps(junk))
    assert installed_python_packages(venv)["typing-extensions"] == ("typing-extensions", "4.16.0")
    found = _by_name(scan_project(tmp_path / "app", venv))
    assert found["httpx"].version == "0.28.1" and "nope" not in found
    assert found["typing-extensions"].direct is False  # installed, not asked for


def test_a_standalone_projects_host_packages_are_listed(tmp_path: Path) -> None:
    found = _by_name(scan_project(tmp_path, None, {"flask": "2.0.1"}))
    assert found["flask"].version == "2.0.1" and found["flask"].file == "host profile"


VULN = {
    "id": "GHSA-aaaa-bbbb-cccc",
    "aliases": ["CVE-2024-0001"],
    "summary": "Prototype pollution",
    "database_specific": {"severity": "HIGH"},
    "affected": [
        {
            "package": {"name": "lodash", "ecosystem": "npm"},
            "ranges": [{"events": [{"introduced": "0"}, {"fixed": "4.17.21"}, {"fixed": "a" * 40}]}],
        }
    ],
}


def _osv_client(requests: list[httpx.Request]) -> osv.ClientFactory:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/querybatch"):
            queries = json.loads(request.content)["queries"]
            results = [
                {"vulns": [{"id": VULN["id"]}]} if q["package"]["name"] == "lodash" else {} for q in queries
            ]
            return httpx.Response(200, json={"results": results})
        return httpx.Response(200, json=VULN)

    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


def test_osv_reports_what_it_finds_and_sends_only_names_and_versions() -> None:
    requests: list[httpx.Request] = []
    deps = [
        Dependency(name="lodash", ecosystem="npm", version="4.17.15"),
        Dependency(name="left-pad", ecosystem="npm", version="1.3.0"),
        Dependency(name="mystery", ecosystem="PyPI"),
    ]
    findings, status = osv.check(deps, _osv_client(requests))
    assert status.status == "ok" and status.checked == 2 and status.found == 1
    [finding] = findings
    assert finding.package == "lodash" and finding.severity == "high"
    assert finding.fixed_in == ["4.17.21"]  # the fixing commit hash is left out
    assert finding.found_by == ["osv.dev"] and finding.link.endswith(finding.id)
    sent = json.loads(requests[0].content)
    assert sent == {
        "queries": [
            {"package": {"name": "lodash", "ecosystem": "npm"}, "version": "4.17.15"},
            {"package": {"name": "left-pad", "ecosystem": "npm"}, "version": "1.3.0"},
        ]
    }


def test_osv_failure_becomes_a_status_not_an_exception() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    def down() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(refuse))

    findings, status = osv.check([Dependency(name="x", ecosystem="PyPI", version="1")], down)
    assert findings == [] and status.status == "unavailable" and "osv.dev" in status.detail


def _fake_pip_audit(stdout: str, code: int = 1) -> audit.Runner:
    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        assert "--no-deps" in command and "--disable-pip" in command
        requirements = Path(command[command.index("-r") + 1]).read_text(encoding="utf-8")
        assert requirements == "Jinja2==2.10\n"  # names and pinned versions only
        return subprocess.CompletedProcess(command, code, stdout, "")

    return run


def test_pip_audit_output_is_parsed() -> None:
    vuln = {
        "id": "PYSEC-2019-1",
        "aliases": ["CVE-2024-0001"],
        "fix_versions": ["2.10.1"],
        "description": "Sandbox",
    }
    report = {"dependencies": [{"name": "jinja2", "version": "2.10", "vulns": [vuln]}]}
    deps = [
        Dependency(name="Jinja2", ecosystem="PyPI", version="2.10"),
        Dependency(name="lodash", ecosystem="npm", version="1"),
    ]
    findings, status = audit.check(deps, _fake_pip_audit(json.dumps(report)))
    assert status.status == "ok" and status.checked == 1  # npm is not its business
    assert findings[0].package == "Jinja2" and findings[0].found_by == ["pip-audit"]
    assert findings[0].fixed_in == ["2.10.1"]


def test_pip_audit_failure_is_reported() -> None:
    deps = [Dependency(name="Jinja2", ecosystem="PyPI", version="2.10")]
    findings, status = audit.check(deps, _fake_pip_audit("not json", 2))
    assert findings == [] and status.status == "unavailable"


def test_the_same_vulnerability_from_two_sources_becomes_one_finding() -> None:
    base = {"package": "Jinja2", "ecosystem": "PyPI", "version": "2.10"}
    a = Finding(
        id="GHSA-1", aliases=["CVE-1"], severity="high", fixed_in=["2.10.1"], found_by=["osv.dev"], **base
    )
    b = Finding(id="PYSEC-1", aliases=["CVE-1"], fixed_in=["2.11"], found_by=["pip-audit"], **base)
    other = Finding(id="GHSA-2", severity="low", found_by=["osv.dev"], **base)
    merged = merge([[a, other], [b]])
    assert len(merged) == 2
    shared = next(f for f in merged if f.id == "GHSA-1")
    assert shared.found_by == ["osv.dev", "pip-audit"] and "PYSEC-1" in shared.aliases
    assert shared.fixed_in == ["2.10.1", "2.11"]
    assert [f.severity for f in merged] == ["high", "low"]  # worst first


def test_run_check_combines_sources_and_counts_unchecked() -> None:
    deps = [
        Dependency(name="lodash", ecosystem="npm", version="4.17.15"),
        Dependency(name="mystery", ecosystem="PyPI"),
    ]
    result = run_check(deps, _osv_client([]), _fake_pip_audit("{}"), _no_licenses())
    assert [s.name for s in result.sources] == ["osv.dev", "pip-audit", "deps.dev"]
    assert result.unchecked == 1
    assert len(result.findings) == 1 and result.findings[0].found_by == ["osv.dev"]


def _no_licenses() -> ClientFactory:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="version not found")

    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


def test_pip_audit_is_given_only_names_it_can_read_and_failures_say_why() -> None:
    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        listed = Path(command[command.index("-r") + 1]).read_text(encoding="utf-8")
        assert listed == "Good==1.0\n"  # a name like '~orge' would make pip-audit reject the whole file
        stderr = "WARNING:pip_audit._cli:a warning\nERROR:pip_audit._cli:requirement file is invalid\n    ^\n"
        return subprocess.CompletedProcess(command, 1, "", stderr)

    deps = [
        Dependency(name="Good", ecosystem="PyPI", version="1.0"),
        Dependency(name="~orge", ecosystem="PyPI", version="1"),
    ]
    findings, status = audit.check(deps, run)
    assert findings == [] and status.status == "unavailable"
    assert "requirement file is invalid" in status.detail  # the ERROR line, not the last line (a caret)
