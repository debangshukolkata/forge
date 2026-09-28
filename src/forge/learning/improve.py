"""Self-improvement proposals (spec §12.5). Forge can never change its own installed code, prompts or
config.yaml — it proposes, and the user decides:

- tier 1 (lesson): stored as a proposed lesson (lessons.py);
- tier 2 (prompt/config tweak): a text added to <forge_home>/prompt_overrides/<prompt>.md, applied ONLY by
  `/improve apply IP-n` (the user types it); config tweaks are shown as a snippet for the user to paste;
- tier 3 (code change): a proposal folder with change.patch and tests; Forge validates it by copying its own
  source into IP-n/sandbox/, applying the patch there and running its test suite (VALIDATION.md).

<forge_home>/improvements/IP-<n>/  PROPOSAL.md, meta.json, change.patch, override.md, tests/, VALIDATION.md
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import forge
from forge.safety.redact import default_redactor

Tier = Literal[1, 2, 3]
PROMPTS = ("system", "system_modeb", "phases")
SOURCE_EXCLUDES = shutil.ignore_patterns(
    ".venv",
    ".venv314",
    "venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "test-artifacts",
    "*.egg-info",
    "node_modules",
)
VALIDATION_TIMEOUT_S = 1800


@dataclass
class Proposal:
    id: str
    folder: Path
    meta: dict[str, Any]


def forge_source_root() -> Path | None:
    """Forge's own source checkout (read-only for Forge): the folder with pyproject.toml above the package."""
    package = Path(forge.__file__).resolve().parent
    for candidate in (package.parent.parent, package.parent):
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / "forge").is_dir():
            return candidate
    return None


class Improvements:
    def __init__(self, home: Path) -> None:
        self.root = home / "improvements"
        self.overrides = home / "prompt_overrides"

    def all(self) -> list[Proposal]:
        if not self.root.exists():
            return []
        proposals = []
        for folder in sorted(self.root.glob("IP-*"), key=lambda p: int(p.name.split("-")[1])):
            meta_path = folder / "meta.json"
            if meta_path.exists():
                proposals.append(
                    Proposal(folder.name, folder, json.loads(meta_path.read_text(encoding="utf-8")))
                )
        return proposals

    def get(self, proposal_id: str) -> Proposal | None:
        return next((p for p in self.all() if p.id.upper() == proposal_id.upper()), None)

    def create(
        self,
        tier: Tier,
        title: str,
        problem: str,
        evidence: str,
        change: str,
        risk: str,
        how_to_test: str,
        *,
        patch: str = "",
        prompt: str | None = None,
        override_text: str = "",
        tests: dict[str, str] | None = None,
    ) -> Proposal:
        if tier == 2 and (prompt not in PROMPTS or not override_text.strip()):
            raise ValueError(f"A tier-2 prompt tweak needs prompt in {PROMPTS} and the text to add.")
        number = len(self.all()) + 1
        folder = self.root / f"IP-{number}"
        folder.mkdir(parents=True)
        clean = default_redactor.redact
        text = (
            f"# IP-{number}: {clean(title)} (tier {tier})\n\n## Problem\n{clean(problem)}\n\n## Evidence\n"
            f"{clean(evidence)}\n\n## Proposed change\n{clean(change)}\n\n## Risk\n{clean(risk)}\n\n"
            f"## How to test\n{clean(how_to_test)}\n"
        )
        (folder / "PROPOSAL.md").write_text(text, encoding="utf-8")
        if patch:
            (folder / "change.patch").write_text(clean(patch), encoding="utf-8")
        if tier == 2:
            (folder / "override.md").write_text(clean(override_text).strip() + "\n", encoding="utf-8")
        for name, body in (tests or {}).items():
            test_path = folder / "tests" / Path(name).name
            test_path.parent.mkdir(exist_ok=True)
            test_path.write_text(clean(body), encoding="utf-8")
        meta = {
            "tier": tier,
            "title": clean(title),
            "status": "proposed",
            "prompt": prompt,
            "created": datetime.now().isoformat(timespec="seconds"),
            "forge_version": forge.__version__,
        }
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return Proposal(folder.name, folder, meta)

    def set_status(self, proposal: Proposal, status: str) -> None:
        proposal.meta["status"] = status
        (proposal.folder / "meta.json").write_text(json.dumps(proposal.meta, indent=1), encoding="utf-8")

    def apply_tier2(self, proposal_id: str) -> str:
        """Only from `/improve apply IP-n`, typed by the user. Adds the override text to the prompt."""
        proposal = self.get(proposal_id)
        if proposal is None:
            raise ValueError(f"No proposal {proposal_id}.")
        if proposal.meta["tier"] != 2:
            raise ValueError(
                "Only tier-2 (prompt/config) proposals can be applied here; tier 3 is applied to "
                "Forge's source by you (see PROPOSAL.md and VALIDATION.md)."
            )
        self.overrides.mkdir(parents=True, exist_ok=True)
        target = self.overrides / f"{proposal.meta['prompt']}.md"
        addition = (proposal.folder / "override.md").read_text(encoding="utf-8")
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(existing + f"\n<!-- {proposal.id} -->\n{addition}", encoding="utf-8")
        self.set_status(proposal, "applied")
        return str(target)

    def validate(
        self, proposal_id: str, pytest_args: tuple[str, ...] = ("-q", "-x", "-p", "no:cacheprovider")
    ) -> str:
        """Tier 3: copy Forge's source into IP-n/sandbox, apply change.patch (+ the proposal's tests), run the
        suite there, and record the result in VALIDATION.md. The installed Forge is never touched."""
        proposal = self.get(proposal_id)
        if proposal is None:
            raise ValueError(f"No proposal {proposal_id}.")
        source = forge_source_root()
        if source is None:
            raise ValueError(
                "Forge's source checkout wasn't found (installed from a wheel): validation needs it."
            )
        sandbox = proposal.folder / "sandbox"
        if sandbox.exists():
            shutil.rmtree(sandbox)
        shutil.copytree(source, sandbox, ignore=SOURCE_EXCLUDES)
        log = [
            f"# Validation of {proposal.id}",
            "",
            f"Source: {source} (copied to sandbox/; not modified)",
            "",
        ]
        patch = proposal.folder / "change.patch"
        applied = True
        if patch.exists():
            result = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(patch)],
                cwd=sandbox,
                capture_output=True,
                text=True,
            )
            applied = result.returncode == 0
            log += [
                "## Patch",
                "applied cleanly" if applied else f"FAILED to apply:\n```\n{result.stderr[-2000:]}\n```",
                "",
            ]
        tests_dir = proposal.folder / "tests"
        if tests_dir.is_dir():
            for test in tests_dir.glob("*.py"):
                shutil.copyfile(test, sandbox / "tests" / test.name)
        passed = False
        if applied:
            env = {**__import__("os").environ, "PYTHONPATH": str(sandbox / "src")}
            run = subprocess.run(
                [sys.executable, "-m", "pytest", *pytest_args],
                cwd=sandbox,
                capture_output=True,
                text=True,
                env=env,
                timeout=VALIDATION_TIMEOUT_S,
            )
            passed = run.returncode == 0
            summary = [
                line
                for line in run.stdout.splitlines()
                if " passed" in line or " failed" in line or "error" in line
            ]
            log += [
                "## Test suite (in the sandbox copy)",
                f"Result: {'PASSED' if passed else 'FAILED'}",
                "```",
                *(summary[-5:] or [run.stdout[-1500:]]),
                "```",
                "",
            ]
        (proposal.folder / "VALIDATION.md").write_text("\n".join(log), encoding="utf-8")
        self.set_status(proposal, "validated" if passed else "validation failed")
        return "\n".join(log)


def prompt_override(home: Path, prompt: str) -> str:
    """Approved tier-2 additions for a built-in prompt (empty when none)."""
    path = home / "prompt_overrides" / f"{prompt}.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""
