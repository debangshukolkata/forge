"""`forge doctor`: checks the environment and reports what works (spec §15). Never prints secret values."""

from __future__ import annotations

import importlib.metadata
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from forge.config import ROLES, ForgeConfig, Secrets, env_file_path, forge_home, load_config, load_secrets
from forge.errors import ForgeError
from forge.llm.base import ChatRequest, Message
from forge.llm.router import LLMRouter
from forge.llm.tokens import count_text_tokens

Status = Literal["ok", "warn", "fail"]
TARGET_PYTHON = (3, 13)
REQUIRED_PACKAGES = (
    "openai",
    "tiktoken",
    "httpx",
    "pydantic",
    "pyyaml",
    "python-dotenv",
    "rich",
    "prompt_toolkit",
    "psutil",
    "psycopg",
)


@dataclass
class CheckResult:
    name: str
    status: Status
    detail: str


def check_python() -> CheckResult:
    version = sys.version_info
    text = f"{version.major}.{version.minor}.{version.micro}"
    if version < (3, 10):
        return CheckResult("Python", "fail", f"{text} — Forge needs 3.10+")
    if (version.major, version.minor) != TARGET_PYTHON:
        return CheckResult("Python", "warn", f"{text} — the office laptop target is 3.13")
    return CheckResult("Python", "ok", text)


def check_packages() -> CheckResult:
    missing, found = [], []
    for package in REQUIRED_PACKAGES:
        try:
            found.append(f"{package} {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
    if missing:
        return CheckResult("Packages", "fail", "missing: " + ", ".join(missing))
    return CheckResult("Packages", "ok", ", ".join(found))


def check_tokenizer() -> CheckResult:
    try:
        count = count_text_tokens("Forge offline tokenizer check")
    except Exception as error:
        return CheckResult("Tokenizer (offline)", "fail", str(error)[:200])
    return CheckResult("Tokenizer (offline)", "ok", f"o200k_base loaded from the package ({count} tokens)")


def check_certificates() -> CheckResult:
    from forge.net import use_system_certificates

    if use_system_certificates():
        return CheckResult(
            "Certificates", "ok", "Windows/OS certificate store (company HTTPS inspection works)"
        )
    return CheckResult(
        "Certificates",
        "warn",
        "Python's bundled list only: behind company HTTPS inspection model calls fail with a certificate "
        "error. Install 'truststore' (it ships with Forge) and leave FORGE_SYSTEM_CERTS unset.",
    )


def check_forge_home(home: Path) -> CheckResult:
    try:
        home.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=home, delete=True):
            pass
    except OSError as error:
        return CheckResult("Forge home", "fail", f"{home} is not writable: {error}")
    return CheckResult("Forge home", "ok", str(home))


def required_secret_names(config: ForgeConfig) -> set[str]:
    """The env var names Forge needs to talk to its configured models (spec §15/D-145's setup screen and
    check_secrets share this one computation — no duplicate list anywhere else)."""
    provider = config.llm.providers.azure
    needed = {provider.endpoint_env, provider.api_key_env, provider.api_version_env}
    needed |= {config.llm.models[key].deployment_env for key in _models_in_use(config)}
    return needed


def missing_secret_names(config: ForgeConfig, secrets: Secrets) -> list[str]:
    """The subset of required_secret_names not currently set — the setup screen's field list (D-145/D-146)
    and the write endpoint's allowlist both derive from this, never a hardcoded duplicate."""
    return sorted(name for name in required_secret_names(config) if not secrets.get(name))


def check_secrets(config: ForgeConfig, secrets: Secrets, home: Path) -> CheckResult:
    missing = missing_secret_names(config, secrets)
    source = secrets.source or env_file_path(home)
    if missing:
        return CheckResult("Secrets", "fail", f"missing in {source}: {', '.join(missing)}")
    needed = required_secret_names(config)
    return CheckResult("Secrets", "ok", f"{len(needed)} required values present in {source}")


async def check_models(config: ForgeConfig, secrets: Secrets) -> list[CheckResult]:
    router = LLMRouter(config, secrets)
    results = []
    for model_key in _models_in_use(config):
        model = config.llm.models[model_key]
        started = time.perf_counter()
        try:
            router.set_role_model("coder", model_key)
            response = await router.chat(
                "coder",
                ChatRequest(
                    messages=[Message.user("Reply with the single word: ready")], max_output_tokens=200
                ),
            )
        except ForgeError as error:
            results.append(CheckResult(f"Model {model_key}", "fail", str(error)[:300]))
            continue
        seconds = time.perf_counter() - started
        provider = router.provider(model_key)
        api = getattr(provider, "api", "?")
        served = response.served_model or "unknown"
        status: Status = "ok" if model.label in served or served == "unknown" else "warn"
        note = "" if status == "ok" else f" (config label is {model.label})"
        results.append(
            CheckResult(
                f"Model {model_key}", status, f"serves {served}{note} via {api} API in {seconds:.1f}s"
            )
        )
    return results


def check_databases(config: ForgeConfig, secrets: Secrets) -> list[CheckResult]:
    """Spec §9.5.2: the access level Forge has on each configured database (L3 write / L2 read / L1 none)."""
    from forge.db.access import AccessLevel, detect
    from forge.db.connection import DbTarget

    results = []
    for name, settings in config.postgres.connections.items():
        label = f"{name.capitalize()} Postgres"
        if not secrets.get(settings.url_env):
            results.append(CheckResult(label, "warn", f"{settings.url_env} not set"))
            continue
        target = DbTarget(name, settings.url_env, settings.sslmode, settings.statement_timeout_s)
        report = detect(target, secrets, None)
        status: Status = "ok" if report.level != AccessLevel.NONE else "warn"
        detail = f"{report.level.value}: {report.reason}"
        if report.can_create_schema:
            detail += "; may create schemas (scratch schemas can be created by Forge)"
        if report.can_write_elsewhere:
            detail += (
                f"; can also write to {', '.join(report.can_write_elsewhere[:5])} (the SQL guard blocks it)"
            )
        results.append(CheckResult(label, status, detail))
    return results


def _models_in_use(config: ForgeConfig) -> list[str]:
    keys = {getattr(config.llm.roles, role) for role in ROLES}
    return sorted(key for key in keys if key)


async def run_doctor(offline: bool = False) -> list[CheckResult]:
    home = forge_home()
    results = [
        check_python(),
        check_packages(),
        check_tokenizer(),
        check_certificates(),
        check_forge_home(home),
    ]
    try:
        config = load_config(home)
    except ForgeError as error:
        return [*results, CheckResult("Config", "fail", str(error)[:500])]
    results.append(CheckResult("Config", "ok", f"{len(config.llm.models)} models, roles valid"))
    secrets = load_secrets(home)
    secrets_result = check_secrets(config, secrets, home)
    results.append(secrets_result)
    results.extend(check_databases(config, secrets))
    if offline:
        results.append(CheckResult("Models", "warn", "skipped (--offline)"))
    elif secrets_result.status == "ok":
        results.extend(await check_models(config, secrets))
    return results


def render_results(results: list[CheckResult], write: Callable[[str], None]) -> None:
    marks = {"ok": "[green]OK  [/green]", "warn": "[yellow]WARN[/yellow]", "fail": "[red]FAIL[/red]"}
    for result in results:
        write(f"{marks[result.status]} {result.name}: {result.detail}")
