"""suggest_model_switch (D-440): for a task that is mainly about pictures, offer once to move the coder to the stronger Azure model.

Measured on 2026-10-15 (a signature cropped out of a prescription photo, the same prompt three times): gpt-5.1 returned a wrong crop twice and reported it as correct, gpt-5.4 returned the whole
signature in the same time. On code tasks gpt-5.4 had shown no gain (D-414), so the default stays and the switch is offered, not forced. When a Gemini model has answered in this
environment the offer is not made: Gemini is the stronger model of the setup (planner, critic, judge) and the user chose to rely on it there. The switch lasts for the session."""

from __future__ import annotations

from pydantic import Field

from forge.config import forge_home, model_secret_names
from forge.environment.plan import _answers
from forge.environment.store import load as load_environment
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.interaction import NOT_AVAILABLE, OptionSpec, _interaction

STRONG_AZURE = "gpt54"
YES = "Yes, use the stronger model for this session"
NO = "No, keep the current model"


class SuggestModelSwitch(Tool):
    name = "suggest_model_switch"
    read_only = True  # it asks; the switch is the user's answer
    description = (
        "Call this ONCE, before you start, when the task is mainly about pictures: cutting something out of a photo or scan, reading handwriting, judging or comparing images, finding a region. "
        "The default model often misjudges such results (it reported wrong crops as correct); the stronger model does not. This asks the user whether to switch this session's coder to the stronger "
        "model, and switches if they agree. It does nothing, and says so, when a Gemini model is available, when the stronger model is not set up, or when it was offered already."
    )

    class Args(ToolArgs):
        reason: str = Field(description="One line: what in the task is about pictures")

    def summary(self, args: SuggestModelSwitch.Args) -> str:
        return "offer the stronger model for a picture task"

    async def run(self, args: SuggestModelSwitch.Args, context: ToolContext) -> ToolResult:
        router = context.router
        if router is None:
            return ToolResult(ok=False, content="No model router in this context.")
        if context.model_switch_asked:
            return ToolResult(ok=True, content="The switch was already offered in this session: carry on.")
        context.model_switch_asked = True
        results = load_environment(forge_home())["results"]
        answered = _answers(router.config, results)
        gemini_up = any(
            ok and key in router.config.llm.models and router.config.llm.models[key].provider == "gemini"
            for key, ok in (answered or {}).items()
        )
        if gemini_up:
            return ToolResult(
                ok=True,
                content="A Gemini model is available here, so no switch is offered: carry on with the current model.",
            )
        model = router.config.llm.models.get(STRONG_AZURE)
        names = model_secret_names(router.config, model) if model else set()
        secrets = context.secrets
        if model is None or (secrets is not None and not all(secrets.get(name) for name in names)):
            return ToolResult(
                ok=True,
                content="The stronger model is not set up on this machine: carry on, and check the result against the source with extra care.",
            )
        if answered is not None and not answered.get(STRONG_AZURE, False):
            return ToolResult(
                ok=True,
                content="The stronger model did not answer the environment test: carry on, and check the result against the source with extra care.",
            )
        if router.model_for_role("coder") == STRONG_AZURE:
            return ToolResult(ok=True, content="The coder is already the stronger model: carry on.")
        interaction = _interaction(context)
        asker = interaction.ask_user if interaction is not None else context.ask_user
        if asker is None:
            return NOT_AVAILABLE
        answer = await asker(
            "This task is mainly about pictures. Switch this session to the stronger model (gpt-5.4)?",
            f"{args.reason}. Measured on a signature crop from a photo: the default model returned a wrong crop twice and said it was right; gpt-5.4 returned the whole signature in the same time. "
            "gpt-5.4 costs more per call on other work, so the switch lasts only for this session.",
            [
                OptionSpec(
                    label=YES,
                    description="Slower and dearer on routine steps, much better at judging pictures.",
                ),
                OptionSpec(
                    label=NO,
                    description="Keep the default model; the result is checked against the source anyway.",
                ),
            ],
            YES,
        )
        if YES.split(",")[0].lower() in str(answer).lower() and NO not in str(answer):
            router.set_role_model("coder", STRONG_AZURE)
            return ToolResult(
                ok=True, content="Switched the coder to gpt-5.4 for this session. Carry on with the task."
            )
        return ToolResult(
            ok=True,
            content="The user kept the current model. Carry on and check the result against the source.",
        )


def model_switch_tools() -> list[Tool]:
    return [SuggestModelSwitch()]
