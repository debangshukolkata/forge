---
id: rcp-pytest
type: recipe
title: Tests that prove something
summary: "Fixtures, parametrize, tmp_path, monkeypatch, injected clocks, property tests and what to assert."
moods: [robust, clean]
products: [testing, any python code]
tags: [pytest, tests, fixtures, hypothesis]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Tests that prove something

Rules: one behaviour per test, named for the behaviour; arrange, act, assert; expected values written by hand from the
requirement, never computed with the code under test; test the error path and the edges (empty, one, many, boundary,
invalid); use `tmp_path` for files, `monkeypatch` for environment variables, a passed-in clock instead of patching `time`;
fake only the outside world (network, clock, disk), not your own functions; a test must fail when the code is wrong.

```python
# runnable
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, tempfile.mkdtemp())
source = Path(sys.path[0])
(source / "pricing.py").write_text(
    "def discount(total: float, member: bool) -> float:\n"
    "    if total < 0:\n        raise ValueError('total cannot be negative')\n"
    "    return round(total * (0.9 if member else 1.0), 2)\n",
    encoding="utf-8",
)
(source / "test_pricing.py").write_text(
    "import pytest\n"
    "from pricing import discount\n\n"
    "@pytest.mark.parametrize(('total', 'member', 'expected'), [(100, True, 90.0), (100, False, 100.0), (0, True, 0.0), (19.99, True, 17.99)])\n"
    "def test_discount(total, member, expected):\n    assert discount(total, member) == expected\n\n"
    "def test_negative_total_is_rejected():\n    with pytest.raises(ValueError, match='negative'):\n        discount(-1, False)\n\n"
    "@pytest.fixture\ndef settings_file(tmp_path):\n    path = tmp_path / 'settings.txt'\n    path.write_text('x=1')\n    return path\n\n"
    "def test_fixture_gives_a_real_file(settings_file):\n    assert settings_file.read_text() == 'x=1'\n",
    encoding="utf-8",
)
import pytest

assert pytest.main(["-q", "-p", "no:cacheprovider", str(source / "test_pricing.py")]) == 0
```

Property tests (`hypothesis`) state a rule that must hold for any input, for example "decode(encode(x)) == x" or "the result
is sorted and has the same items"; use them for parsers, formatters and maths. Coverage tells you what ran, not what was
checked: read the assertions.
