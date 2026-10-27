---
id: rcp-hypothesis
type: recipe
title: Property tests with Hypothesis
summary: "Strategies, round trips and invariants, stateful testing, shrinking, settings profiles, and when not to use it."
moods: [robust, clean]
products: [testing, parsers, formatters, data structures]
tags: [hypothesis, property-based, testing, strategies, stateful]
density: any
dependencies: [hypothesis, pytest]
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: not executed (hypothesis is not installed in the build venv); follows the documented Hypothesis 6 API
---

## Property tests with Hypothesis

A property test states something that must be true for every input of a kind, and the library searches for a counter
example. Use it where the input space is large and the rule is simple to say.

Rules:
- Good properties: a round trip (`decode(encode(x)) == x`), an invariant (output is sorted, same items, length kept),
  idempotence (`normalise(normalise(x)) == normalise(x)`), agreement with a slow obvious version (the oracle), "never
  raises anything but the documented error", and ordering laws (`a + b == b + a` where it should hold).
- Build inputs with strategies: `st.integers(min_value=0, max_value=10**6)`, `st.text()`, `st.lists(...)`,
  `st.dictionaries`, `st.builds(Model, ...)` for dataclasses, `st.composite` for values that depend on each other,
  `st.sampled_from` for fixed choices. Narrow strategies to what the function accepts; filter with `assume` only
  rarely, because filtering most examples away makes the test slow and the health check fails.
- Never write the property as a copy of the implementation; if you do, it proves nothing.
- Failures shrink to a minimal example; keep it as a normal `@example(...)` or a plain regression test so it runs forever.
- Hypothesis stores failing cases in `.hypothesis/`; commit nothing from it, but keep the folder in the CI cache if you can.
- Settings: register profiles in `conftest.py` (`ci` with more examples, `dev` fast) and load by environment variable.
  Do not use `deadline=None` as a habit; a slow example usually points to a real performance problem.

Worked example:

```python
import json
from hypothesis import example, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

settings.register_profile("ci", max_examples=500)
settings.register_profile("dev", max_examples=50)
settings.load_profile("dev")


def slugify(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    return "-".join(part for part in cleaned.split("-") if part)


@given(st.text())
def test_slug_has_only_safe_characters_and_is_idempotent(text):
    slug = slugify(text)
    assert all(ch.isalnum() or ch == "-" for ch in slug)
    assert not slug.startswith("-") and not slug.endswith("-") and "--" not in slug
    assert slugify(slug) == slug


json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(), inner, max_size=4),
    max_leaves=20,
)


@given(json_values)
@example({"": []})  # a case that once broke something, pinned forever
def test_json_round_trip(value):
    assert json.loads(json.dumps(value)) == value


@given(st.lists(st.integers()))
def test_sorted_matches_the_obvious_invariant(items):
    result = sorted(items)
    assert len(result) == len(items)
    assert all(a <= b for a, b in zip(result, result[1:]))
    assert sorted(result) == result


class CounterMachine(RuleBasedStateMachine):
    """Stateful test: random sequences of operations compared with a trivial model."""

    def __init__(self):
        super().__init__()
        self.real = {}  # replace with the object under test, e.g. your LRU cache
        self.model = {}

    @rule(key=st.text(max_size=3), value=st.integers())
    def put(self, key, value):
        self.real[key] = value
        self.model[key] = value

    @rule(key=st.text(max_size=3))
    def remove(self, key):
        self.real.pop(key, None)
        self.model.pop(key, None)

    @invariant()
    def same_contents(self):
        assert self.real == self.model


TestCounter = CounterMachine.TestCase
```

Run with `pytest --hypothesis-show-statistics` to see how many examples were valid, and
`HYPOTHESIS_PROFILE`-style switching via `settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))`.

When not to use it:
- Tests that need a network, a real database or seconds per call (a few hundred examples becomes minutes).
- UI behaviour, or output you can only judge by looking; use example-based tests and snapshots.
- When the property is the implementation. Write three good examples instead.

Gotchas:
- A test that passes with 100 examples can fail on example 5000; the `ci` profile exists for that.
- Strategies that generate huge data (`st.text()` of long strings) slow everything; cap sizes.
- Randomness inside the code under test makes failures unreproducible; inject a seed or a random generator.
- Do not mutate shared fixtures across examples; function-scoped fixtures are not reset between examples, so build state inside the test.
