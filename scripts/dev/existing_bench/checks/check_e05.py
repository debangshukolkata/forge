"""E05: Python 3.7 support is gone from the code and the metadata; version_option still works."""

from __future__ import annotations

import re

import click
from click.testing import CliRunner


def test_click_comes_from_the_delivered_copy(repo):
    assert str(repo) in click.__file__


def test_backport_import_is_gone(repo):
    for path in (repo / "src" / "click").glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "import importlib_metadata" in line:
                raise AssertionError(f"{path.name}: {line.strip()}")


def test_pyproject_drops_the_backport_and_raises_the_minimum(repo):
    text = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "importlib-metadata" not in text and "importlib_metadata" not in text
    match = re.search(r'requires-python\s*=\s*">=\s*3\.(\d+)', text)
    assert match and int(match.group(1)) >= 8


def test_version_option_still_reports_an_installed_package():
    @click.command()
    @click.version_option(package_name="pytest")
    def cli():
        pass

    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output


def test_version_option_missing_package_error():
    @click.command()
    @click.version_option(package_name="definitely-not-installed-xyz")
    def cli():
        pass

    result = CliRunner().invoke(cli, ["--version"])
    assert isinstance(result.exception, RuntimeError)
