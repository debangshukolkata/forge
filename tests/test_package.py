from __future__ import annotations

import subprocess
import sys

import forge
from forge.cli import build_parser


def test_version_is_exposed() -> None:
    assert forge.__version__ == "0.1.0"


def test_cli_has_doctor_subcommand() -> None:
    args = build_parser().parse_args(["doctor", "--offline"])
    assert args.command == "doctor"
    assert args.offline is True


def test_cli_version_flag_via_module() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "forge.cli", "--version"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip().startswith("forge 0.1.0 (build ")  # the build id follows (D-153)
