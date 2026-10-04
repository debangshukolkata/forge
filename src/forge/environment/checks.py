"""Live connectivity checks for the setup screen (D-186). Each check is independent so the screen can show
them finishing one by one. Results carry env var *names* and statuses, never values, and every text
goes through the redactor before it leaves this module."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import asdict, dataclass, field
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
    missing_secret_names,
)
from forge.errors import ForgeError
from forge.safety.redact import default_redactor
from forge.vision.ocr import find_tesseract

Status = Literal["ok", "warn", "fail", "off"]  # off: the user said they do not use it
CHECK_TIMEOUT_S = 90.0
RANK = {"ok": 0, "off": 0, "warn": 1, "fail": 2}


@dataclass
class CheckInfo:
    id: str
    label: str
    optional: bool
    purpose: str
    ask: str = ""  # a yes/no question: the check only runs when the user answers yes (D-201)


CHECKS = (
    CheckInfo("system", "This computer", False, "Python, packages, certificates and the Forge folder"),
    CheckInfo("azure", "Azure OpenAI", False, "The models Forge works with"),
    CheckInfo(
        "postgres_local",
        "Forge database",
        True,
        "Where Forge develops: its own scratch schema for each requirement (LOCAL_PG_URL)",
    ),
    CheckInfo(
        "postgres_dev",
        "Development database (read-only)",
        True,
        "An existing database Forge may read for reference; it never writes to it (DEV_PG_URL)",
    ),
    CheckInfo(
        "gemini",
        "Gemini",
        True,
        "A second model provider (Google Vertex AI); tested with one short call",
        ask="Is Gemini enabled for you?",
    ),
    CheckInfo(
        "tesseract",
        "Tesseract OCR",
        True,
        "Reading text in scanned images (reserved; not used yet)",
        ask="Is Tesseract installed on this computer?",
    ),
)
ASKED_IDS = tuple(check.id for check in CHECKS if check.ask)
KNOWN_IDS = tuple(check.id for check in CHECKS)


@dataclass
class Outcome:
    id: str
    status: Status
    detail: str
    hint: str = ""
    models: dict[str, bool] = field(default_factory=dict)  # azure: model key -> answered
    missing: list[str] = field(default_factory=list)  # azure: env var NAMES not set (never values)
    steps: list[str] = field(
        default_factory=list
    )  # what to do when it does not work: shown under an (i) icon

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["detail"] = default_redactor.redact(self.detail)
        data["hint"] = default_redactor.redact(self.hint)
        return data


def not_in_use(check_id: str, said_no: bool) -> Outcome:
    """What a row shows until the user says yes: nothing is tested (D-201)."""
    detail = "Not in use." if said_no else "Answer the question to test it."
    return Outcome(check_id, "off", detail)


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
            "Add them to the .env file (the setup guide shows where and what), then test again.",
            missing=missing_secret_names(config, secrets),
        )
    models = await check_models(config, secrets)
    answered = {r.name.removeprefix("Model "): r.status != "fail" for r in models}
    outcome = _combine("azure", models, "Check the endpoint, key and deployment names in .env, then retry.")
    outcome.models = answered
    if any(answered.values()) and outcome.status == "fail":
        # Some model answers, so Forge can work: the plan moves the silent one's roles (warn, not stop).
        outcome.status = "warn"
    return outcome


def check_postgres(config: ForgeConfig, which: str) -> Outcome:
    """One database at a time: `local` is the Forge database, `dev` the read-only development database."""
    check_id = f"postgres_{which}"
    setting = config.postgres.connections.get(which)
    if setting is None:
        return Outcome(check_id, "warn", "This database is not configured.", "Nothing to do for now.")
    if not load_secrets(forge_home()).get(setting.url_env):
        return Outcome(
            check_id,
            "warn",
            f"{setting.url_env} is not set.",
            f"Optional: add {setting.url_env} to the .env file, then test again.",
        )
    # Test this one database only: a config that holds just its connection (a failure of the other one is
    # not this row's business, and its connection attempt would only slow this test down).
    single = config.model_copy(
        update={"postgres": config.postgres.model_copy(update={"connections": {which: setting}})}
    )
    results = check_databases(single, load_secrets(forge_home()))
    if not results:
        return Outcome(check_id, "warn", "This database is not configured.", "Nothing to do for now.")
    # The doctor calls "could not connect" a warning; here the URL is set, so a database that does not answer
    # is a failed connection with the reason (the password is redacted from the detail).
    status: Status = "ok" if results[0].status == "ok" else "fail"
    hint = (
        "" if status == "ok" else f"Check {setting.url_env} in the .env file and that PostgreSQL is running."
    )
    return Outcome(check_id, status, results[0].detail, hint)


GEMINI_PROBE_MODEL = "gemini-2.5-flash-lite"  # callable on the user's project; a listing alone proves nothing
GEMINI_STEPS = [
    "Gemini only works on a computer that has Google Cloud access, such as the office laptop. On any other "
    "computer leave the answer above on No; Forge works without it.",
    "Install the package: pip install google-genai",
    "Sign in once: gcloud auth application-default login (or set GOOGLE_APPLICATION_CREDENTIALS to a "
    "service-account file). Forge reads the Google credentials itself; no key goes in the .env file.",
    "Only if the message says no project was found: add GOOGLE_CLOUD_PROJECT to the .env file. "
    "GOOGLE_CLOUD_LOCATION is optional (the default is us-central1).",
    "Use a model your project can call: gemini-2.5-pro, gemini-2.5-flash or gemini-2.5-flash-lite. Others "
    "can be listed yet answer 404 until your Google Cloud admin enables them.",
    "Test again here, or run scripts/dev/gemini_smoke.py to see which part fails.",
]


def _gemini_failed(detail: str) -> Outcome:
    return Outcome(
        "gemini", "fail", detail, "Gemini does not work on this computer; see the steps.", steps=GEMINI_STEPS
    )


def check_gemini(config: ForgeConfig) -> Outcome:
    """Only run when the user said Gemini is enabled (D-201): one short real call."""
    from forge.config import ModelConfig
    from forge.errors import LLMError
    from forge.llm.base import ChatRequest, Message

    provider_config = config.llm.providers.gemini
    secrets = load_secrets(forge_home())
    try:
        from forge.llm.gemini import GeminiProvider
    except ImportError:
        return _gemini_failed("The google-genai package is not installed.")
    model = next((m for m in config.llm.models.values() if m.provider == "gemini"), None) or ModelConfig(
        provider="gemini",
        label="Gemini",
        model_name=GEMINI_PROBE_MODEL,
        context_window=1_000_000,
        max_output=500,
    )

    async def probe() -> str:
        gemini = GeminiProvider("gemini_check", model, provider_config, secrets)
        try:
            # Room for the model's own thinking, which can use up a tight limit and leave no text.
            request = ChatRequest(
                messages=[Message.user("Reply with the single word: ready")], max_output_tokens=500
            )
            return (await gemini.chat(request)).text.strip()
        finally:
            await gemini.close()

    try:
        answer = asyncio.run(probe())
    except LLMError as error:
        return _gemini_failed(str(error)[:300])
    return Outcome("gemini", "ok", f"{model.model_name} answered: {answer or '(no text)'}")


def _ocr_reads_a_test_image(binary: str) -> tuple[bool, str]:
    """Draws the word "Forge" and has the same OCR code the `ocr_image` tool uses read it back: proves the
    install, its language data and the command line work together, not only that the program starts."""
    from PIL import Image, ImageDraw, ImageFont

    from forge.vision.ocr import OcrError, read_image

    image = Image.new("L", (560, 170), 255)
    try:
        font = ImageFont.load_default(size=84)
    except (TypeError, OSError):  # an older Pillow without a sizeable default font
        font = ImageFont.load_default()
    ImageDraw.Draw(image).text((28, 30), "Forge", fill=0, font=font)
    try:
        text = read_image(binary, image, timeout=30)
    except OcrError as error:
        return False, str(error)[:200]
    return "forge" in "".join(ch for ch in text.lower() if ch.isalnum()), ""


def check_tesseract() -> Outcome:
    """Only run when the user said Tesseract is installed (D-201), so not finding it is a failure."""
    found = find_tesseract()
    if not found:
        return Outcome(
            "tesseract",
            "fail",
            "You said it is installed, but Forge cannot find it.",
            "Add its folder to PATH, or answer No above.",
        )
    try:
        completed = subprocess.run(
            [found, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
        lines = (completed.stdout or completed.stderr).splitlines() if completed.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        lines = []
    if not lines:
        return Outcome("tesseract", "fail", f"Found at {found} but it did not run.", "Reinstall Tesseract.")
    reads, problem = _ocr_reads_a_test_image(found)
    if not reads:
        detail = f"{lines[0]} runs, but could not read a test image" + (f": {problem}" if problem else ".")
        return Outcome(
            "tesseract",
            "warn",
            detail,
            "Check that the English language data (eng.traineddata) is installed.",
        )
    return Outcome("tesseract", "ok", f"{lines[0]} read a test image correctly ({found})")


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
            "postgres_local": lambda: check_postgres(config, "local"),
            "postgres_dev": lambda: check_postgres(config, "dev"),
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
