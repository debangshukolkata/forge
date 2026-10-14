"""The approach challenges (tests/benchmarks/challenges): every seed project passes its own tests, and each trap is real (the bug reproduces, the quirk exists)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHALLENGES = Path(__file__).resolve().parent / "benchmarks" / "challenges"
WITH_TESTS = [
    "c01_month_boundary",
    "c02_loyalty_discount",
    "c04_lost_counts",
    "c05_product_search",
    "c06_csv_export",
    "c08_price_refactor",
]


def run(seed: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *arguments], cwd=seed, capture_output=True, text=True, timeout=120)


def test_every_challenge_has_a_task_a_trap_and_a_row_in_the_readme() -> None:
    readme = (CHALLENGES / "README.md").read_text(encoding="utf-8")
    folders = sorted(p for p in CHALLENGES.iterdir() if p.is_dir())
    assert len(folders) == 8
    for folder in folders:
        assert (folder / "task.md").read_text(encoding="utf-8").strip() and (folder / "task.json").is_file()
        assert folder.name in readme


@pytest.mark.parametrize("name", WITH_TESTS)
def test_a_seed_passes_its_own_tests(name: str) -> None:
    done = run(CHALLENGES / name / "seed", "-m", "pytest", "-q", "-p", "no:cacheprovider")
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-400:]


def test_the_month_boundary_bug_is_real() -> None:
    code = (
        "from report import monthly_total_cents; from orders import Order; "
        "print(monthly_total_cents([Order(1, '2026-03-31T20:30:00+00:00', 100)], 2026, 3))"
    )
    assert (
        run(CHALLENGES / "c01_month_boundary" / "seed", "-c", code).stdout.strip() == "100"
    )  # it is 1 April 02:00 in India: March must be 0


def test_the_lost_counts_race_is_real() -> None:
    code = (
        "import threading; from counter import HitCounter\n"
        "c = HitCounter()\n"
        "def work():\n"
        "    for _ in range(1000): c.increment()\n"
        "ts = [threading.Thread(target=work) for _ in range(10)]\n"
        "[t.start() for t in ts]; [t.join() for t in ts]\n"
        "print(c.read())"
    )
    assert int(run(CHALLENGES / "c04_lost_counts" / "seed", "-c", code).stdout.strip()) < 10_000


def test_the_existing_sql_is_injectable() -> None:
    code = (
        "from db import connect; from products import get_user_by_name\n"
        "c = connect(); c.execute(\"INSERT INTO users (name, is_admin) VALUES ('root', 1)\")\n"
        "print(get_user_by_name(c, \"x' OR '1'='1\") is not None)"
    )
    assert run(CHALLENGES / "c05_product_search" / "seed", "-c", code).stdout.strip() == "True"


def test_the_pricing_quirks_exist() -> None:
    code = (
        "from pricing import Customer, Line, price_order\n"
        "bumped = [t for t in range(1_100, 6_000) if (lambda total: total % 5 == 0 and (total - 1) % 5 == 4)(price_order([Line(t, 1)], Customer('standard', 'XX')))]\n"
        "capped = price_order([Line(10_000, 1)], Customer('gold', 'CH'), 50) == price_order([Line(10_000, 1)], Customer('gold', 'CH'), 15)\n"
        "food = price_order([Line(10_000, 1, 'food')], Customer('standard', 'DE')) != price_order([Line(10_000, 1)], Customer('standard', 'DE'))\n"
        "print(len(bumped) > 0, capped, food)"
    )
    assert run(CHALLENGES / "c08_price_refactor" / "seed", "-c", code).stdout.strip() == "True True True"
