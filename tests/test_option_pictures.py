"""D-430: a question option can carry a picture, the candidates note tells the model when to ask, and a headless run answers with the recommended option."""

from __future__ import annotations

from forge.engine.headless import auto_reply
from forge.protocol.events import Event, EventType
from forge.tools.design_candidates import SHOW_CANDIDATES_NOTE
from forge.tools.interaction import AskUser, OptionSpec


def test_an_option_keeps_its_picture_in_the_event_payload() -> None:
    option = OptionSpec(label="Warm", image=".forge/candidates/specimen-a.png")
    assert option.model_dump()["image"] == ".forge/candidates/specimen-a.png"
    assert OptionSpec(label="Plain").model_dump()["image"] == ""
    schema = AskUser.Args.model_json_schema()
    assert "image" in schema["$defs"]["OptionSpec"]["properties"]


def test_the_note_after_the_vote_says_when_to_ask_and_when_not_to() -> None:
    for needed in (
        "ask_user",
        "image",
        "recommended",
        "binding",
        "brief already fixes",
        "asked you not to ask",
    ):
        assert needed in SHOW_CANDIDATES_NOTE


def test_a_headless_run_answers_the_candidate_question_with_the_recommended_option() -> None:
    event = Event(
        seq=1,
        ts="2026-10-15T00:00:00Z",
        type=EventType.QUESTION_ASKED,
        payload={
            "id": "Q1",
            "question": "Which?",
            "options": [{"label": "A"}, {"label": "B"}],
            "recommended": "B",
        },
    )
    reply = auto_reply(event, True)
    assert reply is not None and reply.choice == "B"  # type: ignore[union-attr]
