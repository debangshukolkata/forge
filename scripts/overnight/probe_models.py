"""Which models answer on this machine, as JSON: `python scripts/overnight/probe_models.py [--env-file <.env>]`.

It runs the same two checks as the Environment panel of the web app (`check_azure`, `check_gemini`), so the night's preflight can never disagree with what the user saw there (the first version had its own
probe and missed Gemini and gpt-5.4 on the office laptop although the panel showed them answering). Prints {"gpt54": {"ok": true, "detail": "..."}, "gemini4argon": {"ok": false, "error": "..."}, ...}.
It never prints a key. The overnight runner reads it to decide which jobs can run (a job that needs Gemini is skipped, with the reason, when no Gemini model answers)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def explain(outcome_detail: str, key: str) -> str:
    """The part of a check's text that names this model (the checks join one sentence per model with ';' or '|')."""
    parts = [part.strip() for part in outcome_detail.replace("|", ";").split(";")]
    named = [part for part in parts if key in part]
    return (named[0] if named else outcome_detail)[:300]


def main(env_file: str) -> dict[str, dict[str, object]]:
    if env_file:
        os.environ["FORGE_ENV_FILE"] = env_file
    from forge.config import load_config
    from forge.environment.checks import check_azure, check_gemini
    from forge.net import use_system_certificates

    use_system_certificates()  # the company's HTTPS inspection: the web app does this at start, a separate program must too
    config = load_config()
    found: dict[str, dict[str, object]] = {}

    started = time.time()
    try:
        azure = asyncio.run(check_azure(config))
        if any(not ok for ok in azure.models.values()) and "429" in azure.detail:
            time.sleep(
                75
            )  # a token-rate limit lifts within a minute; one more try before calling the model silent
            azure = asyncio.run(check_azure(config))
        for key, answered in azure.models.items():
            found[key] = (
                {"ok": True, "detail": explain(azure.detail, key)}
                if answered
                else {"ok": False, "error": explain(azure.detail, key)}
            )
        if not azure.models:
            azure_error = azure.detail[:300]
            for key, model in config.llm.models.items():
                if model.provider == "azure":
                    found[key] = {"ok": False, "error": azure_error}
    except Exception as error:  # a failing check is an answer, never a crash
        for key, model in config.llm.models.items():
            if model.provider == "azure":
                found[key] = {"ok": False, "error": f"{type(error).__name__}: {str(error)[:240]}"}
    azure_seconds = round(time.time() - started, 1)

    try:
        gemini = check_gemini(config)  # runs its own event loop per call, so it must not be inside one
        for key, answered in gemini.models.items():
            found[key] = (
                {"ok": True, "detail": explain(gemini.detail, key)}
                if answered
                else {"ok": False, "error": explain(gemini.detail, key)}
            )
    except Exception as error:
        for key, model in config.llm.models.items():
            if model.provider == "gemini":
                found[key] = {"ok": False, "error": f"{type(error).__name__}: {str(error)[:240]}"}

    for key in sorted(config.llm.models):
        found.setdefault(
            key, {"ok": False, "error": "not configured: its names are missing from the .env file"}
        )
    found["_azure_seconds"] = {"ok": True, "seconds": azure_seconds}
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="")
    print(json.dumps(main(parser.parse_args().env_file), indent=1))
