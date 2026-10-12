import random
import subprocess
import sys
import textwrap
from pathlib import Path

import dedupe
from dedupe import count_pairs_with_sum, find_duplicates

FOLDER = Path(dedupe.__file__).resolve().parent


def run_big(snippet: str, limit_s: float = 25.0) -> str:
    """Runs the big case in a separate process so the slow version times out instead of hanging the suite."""
    code = "import random, sys\nsys.path.insert(0, %r)\nfrom dedupe import *\n" % str(
        FOLDER
    ) + textwrap.dedent(snippet)
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=limit_s)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_small_cases_keep_their_meaning() -> None:
    assert find_duplicates([3, 1, 3, 2, 1, 3]) == [3, 1]
    assert find_duplicates([]) == []
    assert find_duplicates(["b", "a", "b", "a", "c"]) == ["b", "a"]
    assert find_duplicates([1, 2, 3]) == []
    assert find_duplicates([(1, 2), (1, 2), (2, 1)]) == [(1, 2)]
    assert count_pairs_with_sum([1, 2, 3, 4, 3], 6) == 2
    assert count_pairs_with_sum([3, 3, 3], 6) == 3
    assert count_pairs_with_sum([], 1) == 0
    assert count_pairs_with_sum([5], 10) == 0
    assert count_pairs_with_sum([-2, 2, 0, 0], 0) == 2


def test_random_inputs_match_the_definition() -> None:
    rng = random.Random(7)
    for _ in range(50):
        numbers = [rng.randint(-5, 5) for _ in range(rng.randint(0, 40))]
        target = rng.randint(-6, 6)
        expected_pairs = sum(
            1
            for i in range(len(numbers))
            for j in range(i + 1, len(numbers))
            if numbers[i] + numbers[j] == target
        )
        assert count_pairs_with_sum(numbers, target) == expected_pairs
        seen: list[int] = []
        for value in numbers:
            if numbers.count(value) > 1 and value not in seen:
                seen.append(value)
        assert find_duplicates(numbers) == seen


def test_find_duplicates_is_fast_on_300k_items() -> None:
    out = run_big(
        """
        rng = random.Random(1)
        data = [rng.randint(0, 200_000) for _ in range(300_000)]
        result = find_duplicates(data)
        print(len(result), result[:3])
        """
    )
    assert out.split(" ")[0].isdigit() and int(out.split(" ")[0]) > 50_000


def test_count_pairs_is_fast_on_300k_items() -> None:
    out = run_big(
        """
        rng = random.Random(2)
        data = [rng.randint(0, 1000) for _ in range(300_000)]
        print(count_pairs_with_sum(data, 1000))
        """
    )
    assert int(out) > 0
