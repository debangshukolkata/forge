"""Everything a UI can send to the engine (spec §15A.2). One model per input kind."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class SendMessage(BaseModel):
    kind: Literal["send_message"] = "send_message"
    text: str


class Answer(BaseModel):
    kind: Literal["answer"] = "answer"
    question_id: str
    choice: str | None = None
    text: str | None = None


class Approve(BaseModel):
    kind: Literal["approve"] = "approve"
    request_id: str
    scope: Literal["once", "prefix"] = "once"  # "prefix": always allow commands starting the same way


class Reject(BaseModel):
    kind: Literal["reject"] = "reject"
    request_id: str
    instruction: str | None = None


class Interrupt(BaseModel):
    kind: Literal["interrupt"] = "interrupt"


class SlashCommand(BaseModel):
    kind: Literal["slash_command"] = "slash_command"
    text: str


class Upload(BaseModel):
    kind: Literal["upload"] = "upload"
    path: str


UserInput = Annotated[
    SendMessage | Answer | Approve | Reject | Interrupt | SlashCommand | Upload, Field(discriminator="kind")
]

user_input_adapter: TypeAdapter[UserInput] = TypeAdapter(UserInput)


def parse_user_input(data: dict[str, object]) -> UserInput:
    """Used by the web UI transport to turn JSON into a typed input."""
    return user_input_adapter.validate_python(data)
