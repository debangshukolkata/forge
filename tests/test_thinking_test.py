"""D-653: the tasks of the model comparison have the answers they claim, and the checks tell right from wrong."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

FILE = Path(__file__).resolve().parent.parent / "scripts" / "dev" / "thinking_test.py"


@pytest.fixture(scope="module")
def kit() -> Any:
    spec = importlib.util.spec_from_file_location("thinking_kit", FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["thinking_kit"] = module
    spec.loader.exec_module(module)
    return module


RIGHT = {
    "parse_time": """
import re
def parse_time(text):
    if not re.fullmatch(r"[0-9]+(:[0-9]+){0,2}", text): raise ValueError(text)
    p = [int(x) for x in text.split(":")]
    if len(p) == 1: return p[0]
    if p[-1] >= 60 or (len(p) == 3 and p[1] >= 60): raise ValueError(text)
    return (p[0] * 3600 + p[1] * 60 + p[2]) if len(p) == 3 else p[0] * 60 + p[1]
""",
    "merge_parts": """
def merge_parts(parts, gap, limit):
    joined = []
    for s, e in sorted(p for p in parts if p[1] > p[0]):
        if joined and s - joined[-1][1] <= gap: joined[-1][1] = max(joined[-1][1], e)
        else: joined.append([s, e])
    out = []
    for s, e in joined:
        while e - s > limit:
            out.append((s, s + limit)); s += limit
        out.append((s, e))
    return out
""",
    "cache": """
from collections import OrderedDict
class Cache:
    def __init__(self, capacity, ttl): self.c, self.t, self.d = capacity, ttl, OrderedDict()
    def _clean(self, now):
        for k in [k for k, (v, at) in self.d.items() if now - at >= self.t]: del self.d[k]
    def get(self, key, now):
        self._clean(now)
        if key not in self.d: return None
        self.d.move_to_end(key); return self.d[key][0]
    def put(self, key, value, now):
        self._clean(now); self.d.pop(key, None)
        if len(self.d) >= self.c: self.d.popitem(last=False)
        self.d[key] = (value, now)
""",
}


def test_the_hidden_checks_accept_a_right_answer_and_refuse_a_wrong_one(kit: Any) -> None:
    assert set(RIGHT) == set(kit.CODE)
    for name, (_, checks) in kit.CODE.items():
        assert kit.passes(RIGHT[name], checks), name
        assert not kit.passes(RIGHT[name].replace(">=", ">").replace("<= gap", "< gap"), checks), name
    assert not kit.passes("while True: pass", "") and not kit.passes("", "parse_time('1')")


def test_the_questions_have_the_answers_they_claim(kit: Any) -> None:
    for name in ("interleaving", "closures"):
        program = kit.EXACT[name][0].split("What does")[0]
        printed = subprocess.run(
            [sys.executable, "-c", program], capture_output=True, text=True, check=True
        ).stdout
        assert [int(n) for n in printed.split()] == list(kit.EXACT[name][1].values())
    rows, offset, done = list(range(1, 11)), 0, []
    while page := rows[offset : offset + 3]:
        done += page
        rows = [r for r in rows if r not in page]
        offset += 3
    assert [r for r in range(1, 11) if r not in done] == kit.EXACT["paging while deleting"][1]["never"]


def test_answers_are_read_from_text_around_them(kit: Any) -> None:
    assert kit.json_in('So: {"rows": 1}\nCorrected:\n```json\n{"rows": 0}\n```') == {"rows": 0}
    assert kit.json_in("none") is None
    assert kit.code_in("Here:\n```python\nx = 1\n```\n") == "x = 1\n"
    good = kit.Variant("a", None, "a", None, exact=6, code=3, design=[0.9], seconds=[2.0], thinking=[100])
    weak = kit.Variant("b", None, "b", None, exact=2)
    assert [line.split()[0] for line in kit.table([weak, good], 1)] == ["model", "a", "b"]
