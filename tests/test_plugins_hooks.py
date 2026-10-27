"""D-501: plugins are folders in DebCraft Home that stay off until enabled; hooks run through the permission gate and can only deny."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.agent.hooks import HookOutcome, HookRunner
from forge.config import HookRule, HooksConfig
from forge.parity.agents import load_agents
from forge.parity.plugins import (
    enabled_names,
    list_plugins,
    plugin_agent_folders,
    plugin_command_folders,
    plugin_hooks,
    plugin_skill_roots,
    set_enabled,
)


def make_plugin(home: Path, name: str = "demo") -> Path:
    folder = home / "plugins" / name
    (folder / "commands").mkdir(parents=True)
    (folder / "agents").mkdir()
    (folder / "skills" / "tidy").mkdir(parents=True)
    (folder / "plugin.json").write_text(
        json.dumps({"name": name, "version": "1.0", "description": "A demo plugin"}), encoding="utf-8"
    )
    (folder / "commands" / "ship.md").write_text("Ship it: $ARGUMENTS", encoding="utf-8")
    (folder / "agents" / "helper.md").write_text(
        "---\ndescription: helps\ntools: read_file\n---\nYou help.", encoding="utf-8"
    )
    (folder / "skills" / "tidy" / "SKILL.md").write_text(
        "---\nname: tidy\ndescription: Use when tidying\n---\nTidy.", encoding="utf-8"
    )
    (folder / "hooks.json").write_text(
        json.dumps({"pre_tool": [{"match": "run_command", "command": "echo checked"}], "bogus": ["x"]}),
        encoding="utf-8",
    )
    return folder


def test_a_plugin_is_off_until_enabled_and_shows_what_it_adds(tmp_path: Path) -> None:
    make_plugin(tmp_path)
    (plugin,) = list_plugins(tmp_path)
    assert not plugin.enabled and plugin.commands == ["ship"] and plugin.agents == ["helper"]
    assert plugin.skills == ["tidy"] and "pre_tool" in plugin.hooks
    shown = plugin.adds()
    assert "/ship" in shown and "helper" in shown and "tidy" in shown and "echo checked" in shown
    assert any(
        "bogus" in problem for problem in plugin.problems
    )  # an unknown hook event is reported, not run
    assert (
        plugin_skill_roots(tmp_path) == [] and plugin_hooks(tmp_path) == {}
    )  # nothing loads while it is off


def test_enabling_keeps_the_rest_of_settings_and_turns_everything_on(tmp_path: Path) -> None:
    make_plugin(tmp_path)
    (tmp_path / "settings.json").write_text(json.dumps({"permissions": {"deny": ["run_command(git push*)"]}}))
    assert set_enabled(tmp_path, "demo", True)
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert data["permissions"] == {"deny": ["run_command(git push*)"]} and enabled_names(tmp_path) == ["demo"]
    assert plugin_command_folders(tmp_path) and plugin_agent_folders(tmp_path)
    assert plugin_skill_roots(tmp_path) == [tmp_path / "plugins" / "demo" / "skills"]
    assert "pre_tool" in plugin_hooks(tmp_path)
    assert "helper" in load_agents(tmp_path)
    assert set_enabled(tmp_path, "demo", False) and enabled_names(tmp_path) == []
    assert not set_enabled(tmp_path, "missing", True)


def test_a_user_agent_replaces_the_plugin_agent_of_the_same_name(tmp_path: Path) -> None:
    make_plugin(tmp_path)
    set_enabled(tmp_path, "demo", True)
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "helper.md").write_text(
        "---\ndescription: mine\n---\nMy helper.", encoding="utf-8"
    )
    assert load_agents(tmp_path)["helper"].prompt == "My helper."


def test_a_plugin_cannot_bring_mcp_servers(tmp_path: Path) -> None:
    folder = make_plugin(tmp_path)
    (folder / "plugin.json").write_text(json.dumps({"name": "demo", "mcp": {"srv": {"command": "x"}}}))
    assert any("MCP" in problem for problem in list_plugins(tmp_path)[0].problems)


def test_the_hook_config_accepts_plain_commands_and_tool_rules() -> None:
    config = HooksConfig(pre_tool=["echo a", {"command": "echo b", "match": "write_*"}])  # type: ignore[list-item]
    assert config.pre_tool[0] == "echo a" and isinstance(config.pre_tool[1], HookRule)


class FakeGate:
    def __init__(self, verdict: str) -> None:
        self.verdict = verdict

    def decide(self, *args: object, **kwargs: object) -> object:
        class Decision:
            verdict = self.verdict
            reason = "test"

        return Decision()


class FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[object, dict[str, object]]] = []

    async def publish(self, kind: object, payload: dict[str, object]) -> None:
        self.events.append((kind, payload))


class FakeContext:
    class shell:
        @staticmethod
        def scope() -> None:
            return None


async def test_a_hook_the_gate_would_ask_about_is_skipped_and_nobody_is_asked() -> None:
    runner = HookRunner({"pre_tool": ["echo hi"]}, FakeContext(), FakeGate("ask"), FakeBus())  # type: ignore[arg-type]
    (outcome,) = await runner.run("pre_tool", "run_command")
    assert not outcome.ran and "cannot approve" in outcome.output
    assert HookRunner.blocked_by([outcome]) is None  # a skipped hook never blocks and never allows


def test_only_a_hook_that_ran_and_failed_blocks() -> None:
    ok = HookOutcome("a", True, True, "")
    failed = HookOutcome("b", True, False, "no pushes on Fridays")
    assert HookRunner.blocked_by([ok, failed]) is failed
    assert HookRunner.blocked_by([ok]) is None


def test_tool_patterns_limit_a_hook_and_user_text_is_never_filled_in() -> None:
    runner = HookRunner(
        {"pre_tool": [{"match": "write_*", "command": "check {tool} {file}"}]},  # type: ignore[list-item]
        FakeContext(),  # type: ignore[arg-type]
        FakeGate("allow"),  # type: ignore[arg-type]
        FakeBus(),  # type: ignore[arg-type]
    )
    assert runner._commands("pre_tool", "read_file", "a.py") == []
    (command,) = runner._commands("pre_tool", "write_file", "a b.py")
    assert command.startswith("check ") and "a b.py" in command and "{" not in command


@pytest.mark.parametrize("event", ["session_start", "session_end", "user_message"])
def test_session_events_ignore_the_tool_pattern(event: str) -> None:
    runner = HookRunner({event: ["echo x"]}, FakeContext(), FakeGate("allow"), FakeBus())  # type: ignore[arg-type]
    assert runner._commands(event, "", "") == ["echo x"]
