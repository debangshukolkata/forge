"""Live connectivity checks for the setup screen (D-186). Each check is independent so the screen can show
them finishing one by one. Results carry env var *names* and statuses, never values, and every text
goes through the redactor before it leaves this module."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from forge.config import ForgeConfig, forge_home, load_config, load_secrets
from forge.doctor import (
    CheckResult,
    check_certificates,
    check_databases,
    check_forge_home,
    check_models,
    check_packages,
    check_python,
    check_secrets,
)
from forge.errors import ForgeError
from forge.safety.redact import default_redactor

Status = Literal["ok", "warn", "fail"]
CHECK_TIMEOUT_S = 90.0
RANK = {"ok": 0, "warn": 1, "fail": 2}


@dataclass
class CheckInfo:
    id: str
    label: str
    optional: bool
    purpose: str


CHECKS = (
    CheckInfo("system", "This computer", False, "Python, packages, certificates and the Forge folder"),
    CheckInfo("azure", "Azure OpenAI", False, "The models Forge works with"),
    CheckInfo("postgres", "PostgreSQL", True, "A database for scratch schemas and data checks"),
    CheckInfo("gemini", "Gemini", True, "Video input (reserved; not used by this version of Forge)"),
    CheckInfo("tesseract", "Tesseract OCR", True, "Reading text in scanned images (reserved; not used yet)"),
)
KNOWN_IDS = tuple(check.id for check in CHECKS)


@dataclass
class Outcome:
    id: str
    status: Status
    detail: str
    hint: str = ""
    models: dict[str, bool] = field(default_factory=dict)  # azure: model key -> answered

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["detail"] = default_redactor.redact(self.detail)
        data["hint"] = default_redactor.redact(self.hint)
        return data


def _worst(results: list[CheckResult]) -> Status:
    return max((r.status for r in results), key=lambda status: RANK[status], default="ok")


def _combine(check_id: str, results: list[CheckResult], hint: str = "") -> Outcome:
    status = _worst(results)
    detail = "; ".join(f"{r.name}: {r.detail}" for r in results)
    return Outcome(check_id, status, detail, hint if status != "ok" else "")


def check_system() -> Outcome:
    results = [check_python(), check_packages(), check_certificates(), check_forge_home(forge_home())]
    outcome = _combine("system", results, "Run `forge doctor` in a terminal for the full report.")
    if outcome.status == "ok":  # nothing to act on: keep the row short
        python = results[0].detail
        outcome.detail = f"Python {python}; packages, certificates and the Forge folder are fine."
    return outcome


async def check_azure(config: ForgeConfig) -> Outcome:
    home = forge_home()
    secrets = load_secrets(home)
    present = check_secrets(config, secrets, home)
    if present.status != "ok":
        return Outcome(
            "azure",
            "fail",
            present.detail,
            "Add the missing values to the .env file in the Forge folder (see .env.example), then retry.",
        )
    models = await check_models(config, secrets)
    answered = {r.name.removeprefix("Model "): r.status != "fail" for r in models}
    outcome = _combine("azure", models, "Check the endpoint, key and deployment names in .env, then retry.")
    outcome.models = answered
    if any(answered.values()) and outcome.status == "fail":
        # Some model answers, so Forge can work: the plan moves the silent one's roles (warn, not stop).
        outcome.status = "warn"
    return outcome


def check_postgres(config: ForgeConfig) -> Outcome:
    results = check_databases(config, load_secrets(forge_home()))
    optional_hint = "Optional: set LOCAL_PG_URL (or DEV_PG_URL) in .env and start PostgreSQL."
    if not results:
        return Outcome("postgres", "warn", "No database is configured.", optional_hint)
    # One reachable database is enough for the scratch-schema features; the detail names each one.
    best = min((r.status for r in results), key=lambda status: RANK[status])
    detail = "; ".join(f"{r.name}: {r.detail}" for r in results)
    return Outcome("postgres", best, detail, "" if best == "ok" else optional_hint)


def _adc_file() -> Path:
    configured = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if configured:
        return Path(configured)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def check_gemini(config: ForgeConfig) -> Outcome:
    provider = getattr(config.llm.providers, "gemini", None)
    if provider is None:
        return Outcome("gemini", "warn", "Not part of this version of Forge.", "Nothing to do for now.")
    secrets = load_secrets(forge_home())
    missing = [name for name in (provider.project_env, provider.location_env) if not secrets.get(name)]
    if missing:
        return Outcome(
            "gemini", "warn", f"missing in .env: {', '.join(missing)}", "Optional: add them to enable video."
        )
    if not _adc_file().exists():
        return Outcome(
            "gemini",
            "warn",
            "No Google application-default credentials found.",
            "Optional: run `gcloud auth application-default login`.",
        )
    return Outcome("gemini", "ok", "Credentials found (not called live).")


def check_tesseract() -> Outcome:
    found = shutil.which("tesseract")
    windows_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if not found and windows_default.exists():
        found = str(windows_default)
    hint = "Optional: install Tesseract and add it to PATH."
    if not found:
        return Outcome("tesseract", "warn", "Not found.", hint)
    try:
        completed = subprocess.run(
            [found, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
        lines = (completed.stdout or completed.stderr).splitlines() if completed.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        lines = []
    if not lines:
        return Outcome("tesseract", "warn", f"Found at {found} but it did not run.", "Reinstall Tesseract.")
    return Outcome("tesseract", "ok", f"{lines[0]} ({found})")


async def run_check(check_id: str) -> Outcome:
    """Runs one check; a crash or a hang becomes a failed check, never an exception to the caller."""
    if check_id not in KNOWN_IDS:
        raise KeyError(check_id)
    try:
        config = load_config(forge_home())
    except ForgeError as error:
        message = f"config.yaml problem: {str(error)[:300]}"
        return Outcome(check_id, "fail", message, "Fix config.yaml and retry.")
    try:
        if check_id == "azure":
            return await asyncio.wait_for(check_azure(config), CHECK_TIMEOUT_S)
        blocking = {
            "system": check_system,
            "postgres": lambda: check_postgres(config),
            "gemini": lambda: check_gemini(config),
            "tesseract": check_tesseract,
        }[check_id]
        return await asyncio.wait_for(asyncio.to_thread(blocking), CHECK_TIMEOUT_S)
    except TimeoutError:
        return Outcome(
            check_id, "fail", f"Timed out after {int(CHECK_TIMEOUT_S)} s.", "Check the network and retry."
        )
    except Exception as error:  # a check must never take the server down
        detail = f"{type(error).__name__}: {str(error)[:200]}"
        return Outcome(check_id, "fail", detail, "Retry; run `forge doctor` for details.")
