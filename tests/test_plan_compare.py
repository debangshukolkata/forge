"""DP2 (D-663): one round of the plan comparison writes three unnamed plans, merged the way DebCraft merges."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx2
import pytest

from tests.helpers import json_response, mocked_router, responses_body, text_output

FOLDER = Path(__file__).resolve().parent.parent / "scripts" / "dev"
MERGED = {
    "plan": "## Objective\nThe merged plan.",
    "differences": [
        {
            "point": "where job ownership is kept",
            "a": "a jobs table",
            "b": "the conversation",
            "chosen": "a",
            "reason": "A new conversation must find the job.",
            "changes_what_is_built": True,
        }
    ],
}


@pytest.fixture(scope="module")
def kit() -> Any:
    sys.path.insert(0, str(FOLDER))
    try:
        return importlib.import_module("plan_compare")
    finally:
        sys.path.remove(str(FOLDER))


async def test_one_round_gives_three_plans_without_their_authors(kit: Any, tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if "You merge two plans" in json.dumps(body):
            return json_response(200, responses_body([text_output(json.dumps(MERGED))]))
        return json_response(200, responses_body([text_output(f"a plan by {body['model']}")]))

    router = mocked_router(handler)
    planners = [
        kit.rc.Candidate("first-model", "gpt51", router),
        kit.rc.Candidate("second-model", "gpt41", router),
    ]
    section, facts = await kit.one_round(planners, planners[0], 1, tmp_path)
    assert sorted(facts["key"].values()) == ["first-model", "merged by first-model", "second-model"]
    assert sorted(facts["key"]) == ["Plan X1", "Plan Y1", "Plan Z1"]
    assert "first-model" not in section and "second-model" not in section  # the page names no author
    assert "## Decided between the two plans" in section and "where job ownership is kept" in section
    assert len(list(tmp_path.glob("Plan_*1.md"))) == 3
    assert facts["differences"][0]["matters"] is True
