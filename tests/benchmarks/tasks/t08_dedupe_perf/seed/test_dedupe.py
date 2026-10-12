from dedupe import count_pairs_with_sum, find_duplicates


def test_find_duplicates() -> None:
    assert find_duplicates([3, 1, 3, 2, 1, 3]) == [3, 1]


def test_count_pairs() -> None:
    assert count_pairs_with_sum([1, 2, 3, 4, 3], 6) == 2
