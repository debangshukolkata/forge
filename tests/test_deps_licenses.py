"""License information in the Dependencies section (D-239): reading installed metadata, the risk categories,
and the deps.dev lookup for libraries that are not installed (at the transport layer: no real network)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from forge.deps import licenses
from forge.deps.license_kinds import classify
from forge.deps.license_read import npm_installed_license, python_installed_licenses
from forge.deps.model import Dependency
from forge.deps.scan import scan_project

LICENSES = {
    "lodash": ["MIT"],
    "psycopg": ["LGPL-3.0-only"],
    "jinja2": ["non-standard"],
    "multi": ["MIT", "Apache-2.0"],
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _by_name(deps: list[Dependency]) -> dict[str, Dependency]:
    return {d.name: d for d in deps}


def _deps_dev_client(asked: list[str]) -> licenses.ClientFactory:
    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        name = request.url.path.split("/packages/")[1].split("/versions/")[0]
        name = name.replace("%40", "@").replace("%2F", "/")
        if name not in LICENSES:
            return httpx.Response(404, text="version not found")
        return httpx.Response(200, json={"licenses": LICENSES[name]})

    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


def test_categories_of_license_names() -> None:
    expected = {
        "MIT": "permissive",
        "Apache Software": "permissive",
        "BSD-3-Clause": "permissive",
        "Python Software Foundation License": "permissive",
        "LGPL-3.0-only": "weak_copyleft",
        "MPL-2.0": "weak_copyleft",
        "GPL-3.0-or-later": "strong_copyleft",
        "GNU General Public License v3 (GPLv3)": "strong_copyleft",
        "AGPL-3.0": "strong_copyleft",
        "MIT OR GPL-2.0": "permissive",  # the user may pick the easier one
        "MIT AND GPL-2.0": "strong_copyleft",  # both apply
        "GPL-2.0 WITH Classpath-exception-2.0": "strong_copyleft",
        "UNKNOWN": "unknown",
        "non-standard": "unknown",
        "": "unknown",
        "Some Company EULA": "unknown",
    }
    assert {text: classify(text) for text in expected} == expected


def test_licenses_are_read_from_installed_metadata(tmp_path: Path) -> None:
    site = tmp_path / "venv" / "Lib" / "site-packages"
    _write(
        site / "newstyle-1.0.dist-info" / "METADATA",
        "Name: newstyle\nLicense-Expression: MIT OR Apache-2.0\n\nbody",
    )
    _write(
        site / "classified-2.0.dist-info" / "METADATA",
        "Name: classified\nClassifier: License :: OSI Approved :: BSD License\n",
    )
    _write(site / "freeform-3.0.dist-info" / "METADATA", "Name: freeform\nLicense: Apache 2.0\n")
    dump = "Permission is hereby granted " * 20  # a whole license text, not a name
    _write(site / "textdump-4.0.dist-info" / "METADATA", f"Name: textdump\nLicense: {dump}\n")
    _write(site / "unknown-5.0.dist-info" / "METADATA", "Name: unknown\nLicense: UNKNOWN\n")
    found = {name: lic for name, (_version, lic) in python_installed_licenses(tmp_path / "venv").items()}
    assert found == {
        "newstyle": "MIT OR Apache-2.0",
        "classified": "BSD",
        "freeform": "Apache 2.0",
        "textdump": "",
        "unknown": "",
    }


def test_npm_license_is_read_and_must_match_the_version(tmp_path: Path) -> None:
    modules = tmp_path / "node_modules"
    _write(modules / "a" / "package.json", json.dumps({"version": "1.0.0", "license": "ISC"}))
    old_style = {"version": "2.0.0", "licenses": [{"type": "MIT"}, {"type": "GPL-2.0"}]}
    _write(modules / "b" / "package.json", json.dumps(old_style))
    assert npm_installed_license(tmp_path, "a", "1.0.0") == "ISC"
    assert npm_installed_license(tmp_path, "a", "9.9.9") == ""  # a different version is installed
    assert npm_installed_license(tmp_path, "b", None) == "MIT OR GPL-2.0"


def test_scan_fills_installed_licenses(tmp_path: Path) -> None:
    _write(tmp_path / "app" / "requirements.txt", "httpx==0.28.1\nabsent==1.0\n")
    info = tmp_path / "venv" / "Lib" / "site-packages" / "httpx-0.28.1.dist-info" / "METADATA"
    _write(info, "Name: httpx\nLicense-Expression: BSD-3-Clause\n")
    found = _by_name(scan_project(tmp_path / "app", tmp_path / "venv"))
    assert found["httpx"].license == "BSD-3-Clause" and found["httpx"].license_source == "installed copy"
    assert found["httpx"].license_category == "permissive"
    assert found["absent"].license == "" and found["absent"].license_category == "unknown"


def test_deps_dev_fills_only_what_is_missing() -> None:
    asked: list[str] = []
    deps = [
        Dependency(name="lodash", ecosystem="npm", version="4.17.15"),
        Dependency(name="psycopg", ecosystem="PyPI", version="3.3.6"),
        Dependency(name="jinja2", ecosystem="PyPI", version="2.10"),
        Dependency(name="multi", ecosystem="PyPI", version="1"),
        Dependency(name="zzz", ecosystem="PyPI", version="1"),
        Dependency(
            name="known", ecosystem="PyPI", version="1", license="MIT", license_source="installed copy"
        ),
        Dependency(name="noversion", ecosystem="PyPI"),
    ]
    status = licenses.fill_licenses(deps, _deps_dev_client(asked))
    by = _by_name(deps)
    assert status.status == "ok" and status.checked == 5 and status.found == 3 and len(asked) == 5
    assert by["lodash"].license == "MIT" and by["lodash"].license_source == "deps.dev"
    assert by["psycopg"].license_category == "weak_copyleft"
    assert by["jinja2"].license == "" and by["zzz"].license == ""  # non-standard / not found stay unknown
    assert by["multi"].license == "MIT AND Apache-2.0"
    assert by["known"].license_source == "installed copy"  # never overwritten


def test_deps_dev_failure_is_a_status() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    def down() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(refuse))

    status = licenses.fill_licenses([Dependency(name="x", ecosystem="PyPI", version="1")], down)
    assert status.status == "unavailable" and "deps.dev" in status.detail


def test_a_leftover_dist_info_folder_is_not_a_package(tmp_path: Path) -> None:
    """A half-removed reinstall leaves '~orge-0.1.0.dist-info'; its name would break pip-audit's input."""
    from forge.deps.scan import installed_python_packages

    site = tmp_path / "venv" / "Lib" / "site-packages"
    _write(site / "~orge-0.1.0.dist-info" / "METADATA", "Name: ~orge\nLicense: MIT\n")
    _write(site / "real-1.0.dist-info" / "METADATA", "Name: real\nLicense: MIT\n")
    assert set(installed_python_packages(tmp_path / "venv")) == {"real"}
    assert set(python_installed_licenses(tmp_path / "venv")) == {"real"}
