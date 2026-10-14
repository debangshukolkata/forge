from counter import HitCounter


def test_increment_counts_one_by_one() -> None:
    counter = HitCounter()
    assert [counter.increment() for _ in range(3)] == [1, 2, 3]
    assert counter.read() == 3
