"""Reads license names from what is already installed (D-239): no network, nothing executed. Python
libraries record theirs in the METADATA file of their `*.dist-info` folder, npm packages in `package.json`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge.deps.model import normalise

HEADER_BYTES = 16_000  # the headers come first; the rest of METADATA is the long description
MAX_LICENSE_CHARS = 120  # a longer "License:" value is the license text itself, not its name


def _metadata_license(metadata: Path) -> str:
    try:
        with metadata.open("rb") as handle:
            text = handle.read(HEADER_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return ""
    header = text.split("\n\n", 1)[0]
    expression = freeform = ""
    classifiers: list[str] = []
    for line in header.splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if key == "License-Expression":
            expression = value
        elif key == "License" and value and len(value) <= MAX_LICENSE_CHARS and "\n" not in value:
            freeform = value
        elif key == "Classifier" and value.startswith("License ::"):
            classifiers.append(value.rsplit("::", 1)[-1].strip().removesuffix(" License"))
    chosen = expression or (classifiers[0] if classifiers else "") or freeform
    return "" if chosen.upper() in {"UNKNOWN", "NONE"} else chosen


def python_installed_licenses(venv: Path) -> dict[str, tuple[str, str]]:
    """normalised name -> (installed version, license name) for every package in a virtual environment."""
    found: dict[str, tuple[str, str]] = {}
    for site in [venv / "Lib" / "site-packages", *sorted((venv / "lib").glob("python*/site-packages"))]:
        if not site.is_dir():
            continue
        for info in site.glob("*.dist-info"):
            name, _, version = info.name[: -len(".dist-info")].rpartition("-")
            if name[:1].isalnum() and version:
                found[normalise(name)] = (version, _metadata_license(info / "METADATA"))
    return found


def npm_installed_license(folder: Path, name: str, version: str | None) -> str:
    """The `license` of node_modules/<name> under `folder`, if that copy is the version asked about."""
    try:
        data: Any = json.loads((folder / "node_modules" / name / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict) or (version is not None and str(data.get("version")) != version):
        return ""
    value = data.get("license")
    if isinstance(value, dict):
        value = value.get("type")
    if not value and isinstance(data.get("licenses"), list):  # the old form: a list of {type, url}
        value = " OR ".join(str(item.get("type", "")) for item in data["licenses"] if isinstance(item, dict))
    return str(value or "").strip()
