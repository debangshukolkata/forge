"""Which models answer on this machine, as JSON: `python scripts/overnight/probe_models.py [--env-file <.env>]`.

Sends one tiny request to every model the configuration lists (Azure and Gemini) with a 90 second limit each, and prints {"gpt51": {"ok": true, "seconds": 2.1}, "gemini4argon": {"ok": false, "error": "..."}, ...}.
It never prints a key. The overnight runner reads it to decide which jobs can run (a job that needs Gemini is skipped, with the reason, when no Gemini model answers)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


async def probe(key: str, router: object, timeout: float) -> dict[str, object]:
    from forge.llm.base import ChatRequest, Message

    started = time.time()
    try:
        provider = router.provider(key)  # type: ignore[attr-defined]
        request = ChatRequest(
            messages=[
                Message.system("Reply with the single word OK."),
                Message(role="user", content="Say OK."),
            ],
            max_output_tokens=3000,
        )
        response = await asyncio.wait_for(provider.chat(request), timeout=timeout)
        return {
            "ok": True,  # no error: the endpoint answered (a reasoning model may spend a small budget on thinking and say nothing)
            "said": str(response.text).strip()[:20],
            "seconds": round(time.time() - started, 1),
            "served": str(getattr(response, "served_model", "")),
        }
    except Exception as error:  # report, never raise: a model that fails is an answer
        return {
            "ok": False,
            "seconds": round(time.time() - started, 1),
            "error": f"{type(error).__name__}: {str(error)[:240]}",
        }


async def main(env_file: str) -> dict[str, dict[str, object]]:
    if env_file:
        os.environ["FORGE_ENV_FILE"] = env_file
    from forge.config import load_config, load_secrets
    from forge.llm.router import LLMRouter

    config = load_config()
    router = LLMRouter(config, load_secrets())
    keys = [key for key in sorted(config.llm.models) if router._configured(key)]
    results = await asyncio.gather(*(probe(key, router, 90.0) for key in keys))
    found = dict(zip(keys, results, strict=True))
    for key in sorted(config.llm.models):
        found.setdefault(
            key, {"ok": False, "error": "not configured: its names are missing from the .env file"}
        )
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="")
    print(json.dumps(asyncio.run(main(parser.parse_args().env_file)), indent=1))
