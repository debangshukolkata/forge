import pytest

from cache import TTLCache


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make(capacity: int = 3, ttl: float = 10.0) -> tuple[TTLCache, Clock]:
    clock = Clock()
    return TTLCache(capacity, ttl, clock=clock), clock


def test_basic_get_set_and_default() -> None:
    cache, _ = make()
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert cache.get("missing") is None
    assert cache.get("missing", "fallback") == "fallback"
    assert "a" in cache and "missing" not in cache
    assert len(cache) == 1


def test_entries_expire_at_exactly_ttl() -> None:
    cache, clock = make(ttl=10)
    cache.set("a", 1)
    clock.now += 9.99
    assert cache.get("a") == 1
    clock.now += 0.01
    assert cache.get("a") is None
    assert "a" not in cache
    assert len(cache) == 0


def test_get_does_not_extend_lifetime_but_set_restarts_it() -> None:
    cache, clock = make(ttl=10)
    cache.set("a", 1)
    clock.now += 6
    assert cache.get("a") == 1
    clock.now += 6
    assert cache.get("a") is None
    cache.set("b", 1)
    clock.now += 6
    cache.set("b", 2)
    clock.now += 6
    assert cache.get("b") == 2


def test_least_recently_used_is_evicted() -> None:
    cache, _ = make(capacity=3)
    for key in "abc":
        cache.set(key, key)
    cache.get("a")  # a is now the most recently used; b is the oldest
    cache.set("d", "d")
    assert "b" not in cache
    assert {"a", "c", "d"} == {k for k in "abcd" if k in cache}
    assert len(cache) == 3


def test_contains_does_not_count_as_use() -> None:
    cache, _ = make(capacity=2)
    cache.set("a", 1)
    cache.set("b", 2)
    assert "a" in cache
    cache.set("c", 3)
    assert "a" not in cache and "b" in cache and "c" in cache


def test_expired_entries_are_dropped_before_live_ones() -> None:
    cache, clock = make(capacity=2, ttl=10)
    cache.set("old", 1)
    clock.now += 5
    cache.set("fresh", 2)
    cache.get("old")  # old was used more recently than fresh... but fresh is newer to store
    clock.now += 5.5  # old expired, fresh still live
    cache.set("new", 3)
    assert cache.get("fresh") == 2
    assert cache.get("new") == 3
    assert len(cache) == 2


def test_delete() -> None:
    cache, clock = make()
    cache.set("a", 1)
    assert cache.delete("a") is True
    assert cache.delete("a") is False
    cache.set("b", 1)
    clock.now += 11
    assert cache.delete("b") is False


def test_len_counts_only_live_entries() -> None:
    cache, clock = make(capacity=5, ttl=10)
    cache.set("a", 1)
    clock.now += 6
    cache.set("b", 2)
    clock.now += 5
    assert len(cache) == 1


def test_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        TTLCache(0, 1)
    with pytest.raises(ValueError):
        TTLCache(1, 0)
    with pytest.raises(ValueError):
        TTLCache(1, -5)


def test_default_clock_works() -> None:
    cache = TTLCache(2, 60)
    cache.set("x", 1)
    assert cache.get("x") == 1
