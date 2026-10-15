r"""A fast check for the work in progress: lint what changed and run only the tests that touch it (D-400).

    python scripts/dev/quick_check.py [--since main] [--browser] [--all-modules]

Finds the files changed since a revision (default HEAD, plus untracked files), runs ruff on the Python ones, and picks the tests to run:
  * a changed test file runs as it is;
  * a changed `src/forge/<package>/<module>.py` runs every test that mentions `forge.<package>.<module>` or `forge.<package>` imports of that module (a text search of tests/);
  * a changed recipe, asset or script runs the tests that name its folder.
Browser tests (marker `browser`) are left out unless `--browser` is given, and live-model tests never run. It prints the command it ran, so the full suite stays one line away:
    .venv\Scripts\python -m pytest -q -n 6 --dist loadfile
Typical time: seconds to a minute, against about seven minutes for everything."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def git_lines(*args: str) -> list[str]:
    done = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def changed_files(since: str) -> list[str]:
    names = set(git_lines("diff", "--name-only", since)) | set(
        git_lines("ls-files", "--others", "--exclude-standard")
    )
    return sorted(name for name in names if (REPO / name).exists())


def tests_for(path: str, tests: dict[str, str]) -> set[str]:
    if path.startswith("tests/test_") and path.endswith(".py"):
        return {Path(path).name}
    wanted: list[str] = []
    if path.startswith("src/forge/") and path.endswith(".py"):
        dotted = path[len("src/") : -3].replace("/", ".")
        wanted.append(dotted.removesuffix(".__init__"))
    elif path.startswith(("src/forge/skills/", "scripts/")):
        wanted.append("/".join(Path(path).parts[:5]))
        wanted.append(Path(path).stem.replace("-", "_"))
    found = set()
    for name, text in tests.items():
        for needle in wanted:
            if needle and re.search(rf"\b{re.escape(needle)}\b", text):
                found.add(name)
                break
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="HEAD")
    parser.add_argument("--browser", action="store_true", help="include the tests that start Edge")
    args = parser.parse_args()
    files = changed_files(args.since)
    if not files:
        print(f"nothing changed since {args.since}")
        return 0
    python_files = [f for f in files if f.endswith(".py")]
    if python_files:
        lint = subprocess.run([str(PYTHON), "-m", "ruff", "check", *python_files], cwd=REPO, check=False)
        if lint.returncode:
            return lint.returncode
    tests = {
        p.name: p.read_text(encoding="utf-8", errors="replace") for p in (REPO / "tests").glob("test_*.py")
    }
    chosen: set[str] = set()
    for path in files:
        chosen |= tests_for(path, tests)
    if not chosen:
        print(f"{len(files)} changed file(s), no test mentions them: lint passed, nothing to run")
        return 0
    command = [
        str(PYTHON),
        "-m",
        "pytest",
        "-q",
        "-n",
        "4",
        "--dist",
        "loadfile",
        *sorted(f"tests/{n}" for n in chosen),
    ]
    if not args.browser:
        command += ["-m", "not browser and not live"]
    print(f"{len(files)} changed, {len(chosen)} test file(s):", " ".join(sorted(chosen)))
    return subprocess.run(command, cwd=REPO, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
