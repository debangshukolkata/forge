"""D-440: suggest_model_switch offers the stronger model once for a picture task, and only when no Gemini model is available."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from forge.config import Secrets, load_config
from forge.llm.router import LLMRouter
from forge.toolkit.base import ToolContext
from forge.tools.model_switch import NO, YES, SuggestModelSwitch
from forge.workspace.create import create_workspace

STRONG_ENV = {
    "AZURE_STRONG_DEPLOYMENT": "x",
    "AZURE_FALLBACK_ENDPOINT": "https://e",
    "AZURE_FALLBACK_API_KEY": "k",  # check_secrets: fake
    "AZURE_FALLBACK_API_VERSION": "v",
}


def make(
    original_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    results: dict[str, Any],
    secrets: dict[str, str],
    answer: str,
) -> tuple[ToolContext, LLMRouter]:
    home = tmp_path / "home"
    home.mkdir()
    (home / "environment.json").write_text(json.dumps({"results": results, "plan": {}}), encoding="utf-8")
    monkeypatch.setenv("FORGE_HOME", str(home))
    router = LLMRouter(load_config(), Secrets(secrets, None))
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), secrets=Secrets(secrets, None)
    )
    context.router = router

    async def ask(question: str, background: str, options: list[Any], recommended: str | None) -> str:
        assert [o.label for o in options] == [YES, NO] and recommended == YES
        return answer

    context.ask_user = ask  # type: ignore[assignment]
    return context, router


async def test_yes_switches_the_coder_and_the_offer_is_made_only_once(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, router = make(
        original_repo,
        tmp_path,
        monkeypatch,
        {"azure": {"models": {"gpt51": True, "gpt54": True}}},
        STRONG_ENV,
        f"The user chose: {YES}",
    )
    assert router.model_for_role("coder") == "gpt51"
    result = await SuggestModelSwitch().run(SuggestModelSwitch.Args(reason="a crop from a photo"), context)
    assert (
        result.ok
        and "Switched the coder to gpt-5.4" in result.content
        and router.model_for_role("coder") == "gpt54"
    )
    again = await SuggestModelSwitch().run(SuggestModelSwitch.Args(reason="x"), context)
    assert "already offered" in again.content


async def test_no_keeps_the_model(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, router = make(
        original_repo,
        tmp_path,
        monkeypatch,
        {"azure": {"models": {"gpt51": True, "gpt54": True}}},
        STRONG_ENV,
        f"The user chose: {NO}",
    )
    result = await SuggestModelSwitch().run(SuggestModelSwitch.Args(reason="x"), context)
    assert "kept the current model" in result.content and router.model_for_role("coder") == "gpt51"


async def test_no_offer_when_gemini_answers_or_the_strong_model_is_missing(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, router = (
        make(
            original_repo,
            tmp_path / "a",
            monkeypatch,
            {"azure": {"models": {"gpt54": True}}, "gemini": {"models": {"gemini31pro": True}}},
            STRONG_ENV,
            f"The user chose: {YES}",
        )
        if (tmp_path / "a").mkdir() is None
        else (None, None)
    )  # type: ignore[misc]
    result = await SuggestModelSwitch().run(SuggestModelSwitch.Args(reason="x"), context)
    assert "Gemini model is available" in result.content and router.model_for_role("coder") == "gpt51"
    (tmp_path / "b").mkdir()
    context2, router2 = make(
        original_repo,
        tmp_path / "b",
        monkeypatch,
        {"azure": {"models": {"gpt51": True}}},
        {},
        f"The user chose: {YES}",
    )
    missing = await SuggestModelSwitch().run(SuggestModelSwitch.Args(reason="x"), context2)
    assert "not set up" in missing.content and router2.model_for_role("coder") == "gpt51"
