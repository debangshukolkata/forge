"""User-pinned interface contracts (spec §6A.2A, D-129): pin, revise, forget, essentials for pinned
context, and the project-memory write when the ContractPin tool is used."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from forge.memory.scope import scope_of
from forge.memory.store import MemoryStore
from forge.modeb.contracts import ContractError, ContractRegister
from forge.modeb.profile import ProfileStore
from forge.modeb.workspace import create_standalone_workspace
from forge.toolkit.base import ToolContext
from forge.tools.modeb import ContractPin, ContractRead
from forge.workspace.workspace import Workspace


@pytest.fixture
def profile(isolated_forge_home: Path) -> object:
    return ProfileStore(isolated_forge_home).create("acme")


@pytest.fixture
def workspace(tmp_path: Path, isolated_forge_home: Path) -> Workspace:
    profile = ProfileStore(isolated_forge_home).create("acme")
    created = create_standalone_workspace(tmp_path / "ws", profile)
    assert created.info.python_env is not None
    created.info.python_env = created.info.python_env.model_copy(update={"python": sys.executable})
    created.save_info()
    return Workspace.open(created.root)


def test_pin_writes_json_and_markdown(profile: object) -> None:
    register = ContractRegister(profile)  # type: ignore[arg-type]

    contract = register.pin(
        "llm_call_wrapper", "def call_llm(prompt: str, **kwargs) -> LLMResponse", "used everywhere"
    )

    assert contract.id == "C1" and contract.seam == "llm_call_wrapper" and contract.source == "user"
    assert register.for_seam("llm_call_wrapper") is not None
    markdown = (profile.root / "CONTRACTS.md").read_text(encoding="utf-8")  # type: ignore[attr-defined]
    assert "llm_call_wrapper" in markdown and "def call_llm" in markdown


def test_pinning_an_existing_seam_revises_it(profile: object) -> None:
    register = ContractRegister(profile)  # type: ignore[arg-type]
    first = register.pin("file_io", "def read(path: str) -> bytes", "")

    revised = register.pin("file_io", "def read(path: Path) -> bytes", "changed after seeing generated code")

    assert revised.id == first.id  # same contract, revised in place (D-129: user may change mid-way)
    assert revised.revised and revised.signature.endswith("bytes")
    assert len(register.all()) == 1


def test_invalid_seam_name_is_rejected(profile: object) -> None:
    register = ContractRegister(profile)  # type: ignore[arg-type]

    with pytest.raises(ContractError):
        register.pin("Not A Valid Seam!", "def x() -> None", "")


def test_forget_removes_a_contract(profile: object) -> None:
    register = ContractRegister(profile)  # type: ignore[arg-type]
    register.pin("file_io", "def read(path: str) -> bytes", "")

    assert register.forget("file_io")
    assert register.for_seam("file_io") is None
    assert not register.forget("file_io")  # already gone


def test_essentials_is_empty_until_something_is_pinned(profile: object) -> None:
    register = ContractRegister(profile)  # type: ignore[arg-type]
    assert register.essentials() == ""

    register.pin("llm_call_wrapper", "def call_llm(prompt: str) -> str", "")

    essentials = register.essentials()
    assert "llm_call_wrapper" in essentials and "def call_llm" in essentials


def test_sensitive_terms_are_masked_in_pinned_signatures(isolated_forge_home: Path) -> None:
    profile = ProfileStore(isolated_forge_home).create("acme", ["Acme Corp"])
    register = ContractRegister(profile)

    contract = register.pin("file_io", "def read(path: str) -> AcmeCorpFile", "for Acme Corp only")

    assert "Acme Corp" not in contract.signature and "Acme Corp" not in contract.note


# --- tool layer ---


async def test_contract_pin_tool_saves_and_remembers_the_contract(
    workspace: Workspace, isolated_forge_home: Path
) -> None:
    from forge.modeb.profile import ProfileStore as _Store

    profile = _Store(isolated_forge_home).open("acme")
    context = ToolContext(workspace=workspace, profile=profile)

    result = await ContractPin().run(
        ContractPin.Args(
            seam="llm_call_wrapper",
            signature="def call_llm(prompt: str, **kwargs) -> LLMResponse",
            note="the only entry point for LLM calls",
        ),
        context,
    )

    assert result.ok and "C1" in result.content
    listed = await ContractRead().run(ContractRead.Args(), context)
    assert "llm_call_wrapper" in listed.content and "call_llm" in listed.content

    remembered = MemoryStore(isolated_forge_home, scope_of(workspace)).get("contract-llm-call-wrapper")
    assert remembered is not None and "call_llm" in remembered.text and remembered.kind == "reference"


async def test_contract_pin_tool_without_a_profile_fails_cleanly(
    tmp_path: Path, isolated_forge_home: Path
) -> None:
    from forge.workspace.create import create_workspace
    from tests.conftest import FIXTURE_REPO

    mode_a_workspace = create_workspace(FIXTURE_REPO, tmp_path / "wsa", "backend")
    context = ToolContext(workspace=mode_a_workspace)  # no profile: Mode A

    result = await ContractPin().run(
        ContractPin.Args(seam="x", signature="def x() -> None", note=""), context
    )

    assert not result.ok and "No host profile" in result.content
