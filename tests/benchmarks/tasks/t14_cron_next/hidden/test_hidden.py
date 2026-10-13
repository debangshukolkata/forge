from __future__ import annotations

import time
from datetime import datetime

import pytest

from cron import next_run


def d(text: str) -> datetime:
    return datetime.fromisoformat(text)


@pytest.mark.parametrize(
    "expression,after,expected",
    [
        ("* * * * *", "2024-05-01 10:00:30", "2024-05-01 10:01:00"),
        ("* * * * *", "2024-05-01 10:00:00", "2024-05-01 10:01:00"),
        ("* * * * *", "2024-05-01 10:00:00.999999", "2024-05-01 10:01:00"),
        ("*/15 * * * *", "2024-05-01 10:14:59", "2024-05-01 10:15:00"),
        ("*/15 * * * *", "2024-05-01 10:45:00", "2024-05-01 11:00:00"),
        ("30 9 * * *", "2024-05-01 09:30:00", "2024-05-02 09:30:00"),
        ("30 9 * * *", "2024-05-01 09:29:59", "2024-05-01 09:30:00"),
        ("0 0 1 1 *", "2024-05-01 00:00:00", "2025-01-01 00:00:00"),
        ("59 23 31 12 *", "2024-12-31 23:59:00", "2025-12-31 23:59:00"),
        ("0 0 29 2 *", "2023-03-01 00:00:00", "2024-02-29 00:00:00"),
        ("0 0 29 2 *", "2024-02-29 00:00:00", "2028-02-29 00:00:00"),
        ("0 12 31 * *", "2024-04-15 00:00:00", "2024-05-31 12:00:00"),
        ("0 0 31 * *", "2024-01-31 00:00:00", "2024-03-31 00:00:00"),
        ("10-40/10 * * * *", "2024-05-01 10:00:00", "2024-05-01 10:10:00"),
        ("10-40/10 * * * *", "2024-05-01 10:40:00", "2024-05-01 11:10:00"),
        ("5/20 * * * *", "2024-05-01 10:06:00", "2024-05-01 10:25:00"),
        ("5/20 * * * *", "2024-05-01 10:46:00", "2024-05-01 11:05:00"),
        ("0,30 8,17 * * *", "2024-05-01 08:30:00", "2024-05-01 17:00:00"),
        ("0 9 * * mon-fri", "2024-05-03 09:00:00", "2024-05-06 09:00:00"),  # Fri -> Mon
        ("0 9 * * MON-FRI", "2024-05-04 00:00:00", "2024-05-06 09:00:00"),  # Saturday
        ("0 0 * * 0", "2024-05-01 00:00:00", "2024-05-05 00:00:00"),  # Sunday
        ("0 0 * * 7", "2024-05-01 00:00:00", "2024-05-05 00:00:00"),
        ("0 0 * * 5-7", "2024-05-02 00:00:00", "2024-05-03 00:00:00"),
        ("0 0 * * sun", "2024-05-05 00:00:00", "2024-05-12 00:00:00"),
        ("0 0 1 jan,JUL *", "2024-02-01 00:00:00", "2024-07-01 00:00:00"),
        ("0 0 1 mar-may *", "2024-05-01 00:00:00", "2025-03-01 00:00:00"),
        ("0 0 * feb *", "2024-02-28 12:00:00", "2024-02-29 00:00:00"),
        ("*/2 * * * *", "2024-05-01 23:59:00", "2024-05-02 00:00:00"),
        ("  15   10\t* * *  ", "2024-05-01 00:00:00", "2024-05-01 10:15:00"),
    ],
)
def test_next_run(expression: str, after: str, expected: str) -> None:
    result = next_run(expression, d(after))
    assert result == d(expected)
    assert result.second == 0 and result.microsecond == 0


def test_either_day_field_matches_when_both_are_restricted() -> None:
    # the 1st and 15th, or any Friday
    expression = "0 4 1,15 * 5"
    assert next_run(expression, d("2024-05-01 04:00:00")) == d("2024-05-03 04:00:00")  # Fri 3rd
    assert next_run(expression, d("2024-05-03 04:00:00")) == d("2024-05-10 04:00:00")
    assert next_run(expression, d("2024-05-10 04:00:00")) == d("2024-05-15 04:00:00")  # 15th, a Wednesday
    assert next_run(expression, d("2024-05-15 04:00:00")) == d("2024-05-17 04:00:00")


def test_a_star_field_means_the_other_one_alone() -> None:
    assert next_run("0 0 * * 1", d("2024-05-01 00:00:00")) == d("2024-05-06 00:00:00")
    assert next_run("0 0 15 * *", d("2024-05-01 00:00:00")) == d("2024-05-15 00:00:00")


def test_a_step_star_day_of_month_is_combined_with_the_weekday_by_and() -> None:
    # odd days that are also Mondays: 2024-05-06 is an even day; the next odd Monday is the 13th
    assert next_run("0 0 */2 * 1", d("2024-05-01 00:00:00")) == d("2024-05-13 00:00:00")


def test_seven_is_sunday_in_lists_and_steps() -> None:
    assert next_run("0 0 * * 6,7", d("2024-05-01 00:00:00")) == d("2024-05-04 00:00:00")
    assert next_run("0 0 * * 0,7", d("2024-05-05 00:00:00")) == d("2024-05-12 00:00:00")


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "* * * *",
        "* * * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * 32 * *",
        "* * * 13 *",
        "* * * 0 *",
        "* * * * 8",
        "5-2 * * * *",
        "*/0 * * * *",
        "*/x * * * *",
        "1,,2 * * * *",
        "1, * * * *",
        "* * * foo *",
        "* * * * funday",
        "mon * * * *",
        "* jan * * *",
        "a * * * *",
        "-5 * * * *",
        "5- * * * *",
        "1-2-3 * * * *",
        "*/-1 * * * *",
        "? * * * *",
        "@daily",
    ],
)
def test_invalid_expressions_raise_value_error(expression: str) -> None:
    with pytest.raises(ValueError):
        next_run(expression, d("2024-05-01 00:00:00"))


@pytest.mark.parametrize("expression", ["0 0 30 2 *", "0 0 31 4,6,9,11 *", "0 0 31 2 *"])
def test_expressions_that_can_never_fire_raise_quickly(expression: str) -> None:
    started = time.perf_counter()
    with pytest.raises(ValueError):
        next_run(expression, d("2024-05-01 00:00:00"))
    assert time.perf_counter() - started < 2.0


def test_leap_day_found_across_the_century_gap_is_not_needed_but_8_years_is_enough() -> None:
    assert next_run("0 0 29 2 *", d("2024-03-01 00:00:00")) == d("2028-02-29 00:00:00")


def test_sparse_expression_is_fast() -> None:
    started = time.perf_counter()
    assert next_run("59 23 31 12 *", d("2024-01-01 00:00:00")) == d("2024-12-31 23:59:00")
    assert time.perf_counter() - started < 1.0


def test_result_is_a_fresh_naive_datetime() -> None:
    result = next_run("* * * * *", d("2024-05-01 10:00:00"))
    assert result.tzinfo is None and isinstance(result, datetime)
