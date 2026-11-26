"""Two planners, one plan (D-658): who plans, the merge, the questions, and the plan the coder gets."""

from __future__ import annotations

import json
from typing import Any

import httpx2

from forge.llm.base import ChatRequest, Message
from forge.subagents import dual_plan
from forge.subagents.dual_plan import Difference, Merged
from forge.toolkit.base import ToolContext
from tests.helpers import json_response, mocked_router, responses_body, text_output

MERGED = {
    "plan": "## Objective\nAnswer questions about a recording with the model.",
    "differences": [
        {
            "point": "how questions are answered",
            "a": "ask the model with the stored sections",
            "b": "compare the words of the question with the sections",
            "chosen": "a",
            "reason": "Reworded questions must be found.",
            "changes_what_is_built": True,
        },
        {
            "point": "file name",
            "a": "qa.py",
            "b": "answers.py",
            "chosen": "b",
            "reason": "",
            "changes_what_is_built": False,
        },
    ],
}


def _router(merge_answer: str, served: list[str]):  # type: ignore[no-untyped-def]
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        served.append(body["model"])
        if "You merge two plans" in json.dumps(body):
            return json_response(200, responses_body([text_output(merge_answer)]))
        return json_response(200, responses_body([text_output(f"plan written by {body['model']}")]))

    router = mocked_router(handler)
    router.config.llm.plan_twice = ["gpt51", "gpt41"]
    router.config.llm.plan_merger = "gpt4o"
    return router


def _context(tmp_path: Any, asked: list[tuple[str, list[Any], str | None]], pick: str | None) -> ToolContext:
    async def ask(question: str, context: str, options: list[Any], recommended: str | None) -> str:
        asked.append((question, options, recommended))
        return f"The user chose: {pick or recommended}"

    context = ToolContext.__new__(ToolContext)
    context.interaction = None
    context.ask_user = ask
    return context


async def test_both_plan_with_their_own_model_and_the_user_decides_what_changes_the_result(
    tmp_path: Any,
) -> None:
    served: list[str] = []
    router = _router(json.dumps(MERGED), served)
    plans: list[str] = []

    async def plan_once() -> str:
        text = (await router.chat("planner", ChatRequest(messages=[Message.user("plan")]))).text
        plans.append(text)
        return text

    asked: list[tuple[str, list[Any], str | None]] = []
    keys = dual_plan.planners(router)
    assert keys == ["gpt51", "gpt41"]
    pick = "compare the words of the question with the sections"
    result = await dual_plan.plan_twice(router, _context(tmp_path, asked, pick), keys, plan_once, "the task")
    assert sorted(plans) == ["plan written by primary-deployment", "plan written by secondary-deployment"]
    assert (
        len(asked) == 1 and asked[0][0] == "Two plans differ: how questions are answered"
    )  # the file name is not asked
    assert asked[0][2] == "ask the model with the stored sections"
    assert result.startswith("## Objective")
    assert "**how questions are answered**: compare the words" in result and "chosen by the user" in result
    assert "**file name**: answers.py (chosen by the merging model" in result


async def test_one_plan_when_the_other_fails_and_both_plans_when_the_merge_is_not_json(tmp_path: Any) -> None:
    served: list[str] = []
    router = _router("I would rather not.", served)
    calls = 0

    async def plan_once() -> str:
        nonlocal calls
        calls += 1
        return (await router.chat("planner", ChatRequest(messages=[Message.user("plan")]))).text

    result = await dual_plan.plan_twice(
        router, _context(tmp_path, [], None), ["gpt51", "gpt41"], plan_once, "t"
    )
    assert "## Plan A" in result and "## Plan B" in result and calls == 2

    async def failing_once() -> str:
        if dual_plan.forced_model.get() == ("planner", "gpt41"):
            raise RuntimeError("down")
        return "the only plan"

    assert (
        await dual_plan.plan_twice(
            router, _context(tmp_path, [], None), ["gpt51", "gpt41"], failing_once, "t"
        )
        == "the only plan"
    )

    async def unreachable_once() -> str:
        if dual_plan.forced_model.get() is not None:
            raise RuntimeError("the model cannot be reached")
        return "the planner role alone"

    assert (
        await dual_plan.plan_twice(
            router, _context(tmp_path, [], None), ["gpt51", "gpt41"], unreachable_once, "t"
        )
        == "the planner role alone"
    )


def test_one_planner_when_fewer_than_two_are_set_up() -> None:
    router = _router("{}", [])
    router.config.llm.plan_twice = ["gpt51", "unknown-model"]
    assert dual_plan.planners(router) == []
    router.config.llm.plan_twice = []
    assert dual_plan.planners(router) == []


def test_parse_merge_takes_the_json_out_of_the_answer_and_refuses_anything_else() -> None:
    merged = dual_plan.parse_merge("Here it is:\n```json\n" + json.dumps(MERGED) + "\n```")
    assert merged is not None and [d.matters for d in merged.differences] == [True, False]
    assert dual_plan.parse_merge("no json") is None
    assert dual_plan.parse_merge('{"plan": ""}') is None


def test_the_report_says_when_both_agreed() -> None:
    assert "agreed on every point" in dual_plan.report(Merged(plan="P"))
    text = dual_plan.report(Merged(plan="P", differences=[Difference("x", "one", "two", "b", "why", False)]))
    assert "**x**: two (chosen by the merging model; not: one). why" in text


async def test_the_forced_model_applies_to_the_planner_only() -> None:
    served: list[str] = []
    router = _router("{}", served)
    token = dual_plan.forced_model.set(("planner", "gpt41"))
    try:
        await router.chat("planner", ChatRequest(messages=[Message.user("a")]))
        await router.chat("summariser", ChatRequest(messages=[Message.user("b")]))
    finally:
        dual_plan.forced_model.reset(token)
    assert served[0] == "secondary-deployment" and served[1] != "secondary-deployment"


async def test_the_merge_is_done_by_the_plan_merger_and_by_the_judge_when_it_is_not_set_up(
    tmp_path: Any,
) -> None:
    served: list[str] = []
    router = _router(json.dumps(MERGED), served)

    async def plan_once() -> str:
        return "a plan " + str(dual_plan.forced_model.get())

    await dual_plan.plan_twice(router, _context(tmp_path, [], None), ["gpt51", "gpt41"], plan_once, "t")
    merger = router.config.llm.models["gpt4o"]
    assert served[-1] == router._secrets.get(merger.deployment_env)
    served.clear()
    router.config.llm.plan_merger = "not-a-model"
    await dual_plan.plan_twice(router, _context(tmp_path, [], None), ["gpt51", "gpt41"], plan_once, "t")
    judge = router.config.llm.models[router.model_for_role("judge")]
    assert served[-1] == router._secrets.get(judge.deployment_env)
