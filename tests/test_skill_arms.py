"""The skill arms experiment (C16): arm and environment construction and the pre-flight listing. No model, no benchmark run."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark" / "run_skill_arms.py"


@pytest.fixture(scope="module")
def arms_module():
    spec = importlib.util.spec_from_file_location("run_skill_arms", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_skill_arms"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("FORGE_DISABLED_SKILLS", raising=False)
    monkeypatch.delenv("FORGE_EXTRA_SKILLS_DIR", raising=False)


def fake_set(root: Path, *names: str) -> Path:
    for name in names:
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: fake {name}\n---\nbody\n", encoding="utf-8"
        )
    return root


def test_baseline_and_distilled_env(arms_module):
    baseline, distilled = arms_module.build_arms(["baseline", "distilled"])
    assert baseline.env_pairs() == [f"FORGE_DISABLED_SKILLS={','.join(arms_module.WORKFLOW_SKILLS)}"]
    assert distilled.env_pairs() == []
    assert "python-project" not in baseline.disabled


def test_external_arm_skipped_without_folder(arms_module):
    arms = arms_module.build_arms(["superpowers", "mattpocock"])
    assert all(arm.skip_reason for arm in arms)
    assert "--superpowers-dir not given" in arms[0].skip_reason


def test_external_arm_skipped_for_empty_folder(arms_module, tmp_path):
    (tmp_path / "empty").mkdir()
    arm = arms_module.build_arms(["superpowers"], superpowers_dir=str(tmp_path / "empty"))[0]
    assert "no <skill>/SKILL.md" in arm.skip_reason


def test_external_arm_env_and_visibility(arms_module, tmp_path):
    folder = fake_set(tmp_path / "sp", "brainstorming", "systematic-debugging")
    arm = arms_module.build_arms(["superpowers"], superpowers_dir=str(folder))[0]
    assert not arm.skip_reason
    pairs = dict(p.split("=", 1) for p in arm.env_pairs())
    assert pairs["FORGE_EXTRA_SKILLS_DIR"] == str(folder)
    assert set(pairs["FORGE_DISABLED_SKILLS"].split(",")) == set(arms_module.WORKFLOW_SKILLS)
    seen = arms_module.visible_skills(arm)
    assert "brainstorming" in seen and "systematic-debugging" in seen
    assert "test-first" not in seen and "python-project" in seen
    assert "FORGE_EXTRA_SKILLS_DIR" not in os.environ  # the listing leaves the process environment as it was


def test_external_skill_with_a_workflow_name_replaces_ours(arms_module, tmp_path):
    folder = fake_set(tmp_path / "mp", "debugging", "grill-me")
    arm = arms_module.build_arms(["mattpocock"], mattpocock_dir=str(folder))[0]
    assert "debugging" not in arm.disabled
    seen = arms_module.visible_skills(arm)
    assert "debugging" in seen and "grill-me" in seen
    assert "note: these replace" in arms_module.preflight([arm])


def test_preflight_lists_skipped_and_setup_warning(arms_module, tmp_path):
    folder = fake_set(tmp_path / "mp", "setup-repo", "tdd")
    arms = arms_module.build_arms(["baseline", "mattpocock", "superpowers"], mattpocock_dir=str(folder))
    text = arms_module.preflight(arms)
    assert "- baseline:" in text and "disabled: test-first" in text
    assert "- superpowers: SKIPPED" in text
    assert "WARNING: setup-repo" in text


def test_extra_skills_env_is_read_by_discover(tmp_path, monkeypatch):
    from forge.parity.skills import discover

    first = fake_set(tmp_path / "a", "alpha")
    second = fake_set(tmp_path / "b", "beta")
    monkeypatch.setenv("FORGE_EXTRA_SKILLS_DIR", os.pathsep.join([str(first), str(second)]))
    found = discover()
    assert {"alpha", "beta"} <= set(found)


def test_run_names_and_slowdown_note(arms_module):
    assert arms_module.run_name("arms1", "baseline", 2) == "arms1-baseline-2"
    results = {
        "baseline": [[{"id": "t01_slugify", "wall_s": 100}, {"id": "t11_rate_limiter", "wall_s": 500}]],
        "distilled": [[{"id": "t01_slugify", "wall_s": 150}]],
    }
    note = arms_module.slowdown_note(results)
    assert "+50 percent" in note
    table = arms_module.compare_arms(results)
    assert "| baseline | 1 |" in table and "t11_rate_limiter" in table
