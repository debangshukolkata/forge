---
id: rcp-refactoring
type: recipe
title: Refactoring in small safe steps
summary: "Guard clauses, extract function, table instead of if-chains, remove duplication, keep the tests green."
moods: [clean]
products: [refactor, any python code]
tags: [refactoring, clean code, duplication, readability]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Refactoring in small safe steps

Rules: tests first (or write characterisation tests that pin what the code does now); change structure in tiny steps and run
the tests after each one; never mix a refactor with a behaviour change in the same step; stop when the code reads clearly,
not when it is clever.

Common moves:
- **Guard clauses** instead of deep nesting: handle the invalid or empty cases first and return/raise early.
- **Extract function** when a block has a name you can say out loud; the function does one thing.
- **Table instead of an if-chain**: a dict of key to value or key to function.
- **One place for each rule**: a constant or function for each tax rate, limit or message, not copies.
- **Replace flags and parallel lists** with a small dataclass.
- **Delete** dead code and unused parameters; do not comment it out.

```python
# runnable
from dataclasses import dataclass


# before: nested, repeated, magic numbers
def shipping_before(country, weight, express):
    if country == "IN":
        if weight < 1:
            return 40 if not express else 90
        else:
            return 60 if not express else 120
    elif country == "US":
        if weight < 1:
            return 400 if not express else 900
        else:
            return 600 if not express else 1200
    else:
        raise ValueError("unknown country")


# after: data in a table, one rule for weight and speed
@dataclass(frozen=True)
class Rate:
    light: int
    heavy: int


RATES = {"IN": Rate(40, 60), "US": Rate(400, 600)}
EXPRESS_LIGHT, EXPRESS_HEAVY = (
    2.25,
    2,
)  # express multiplies the base rate; the old code had these baked into its numbers


def shipping_after(country: str, weight: float, express: bool) -> int:
    if country not in RATES:
        raise ValueError("unknown country")
    rate = RATES[country]
    base = rate.light if weight < 1 else rate.heavy
    if not express:
        return base
    return int(base * (EXPRESS_LIGHT if weight < 1 else EXPRESS_HEAVY))


for country in ("IN", "US"):
    for weight in (0.5, 1, 7):
        for express in (False, True):
            assert shipping_before(country, weight, express) == shipping_after(country, weight, express)
```

The loop at the end is the safety net: the old and new versions agree on every input before the old one is deleted.
