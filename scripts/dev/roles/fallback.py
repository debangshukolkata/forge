"""Fallback: going on with work another model began (D-655).

A small loop with made-up tools: the first half of the work is in the history as another model's tool calls. Scored by
hidden checks, with a deduction for work that is done again, calls that do not exist, and not finishing."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from forge.llm.base import ChatRequest, LLMResponse, Message, ToolCall, ToolSpec

MAX_STEPS = 14
REQUEST = (
    "Split the module shop.py: put the prices into prices.py (load_prices, price_of) and the basket into basket.py "
    "(class Basket with add(name, count=1), total() and remove(name)). total() gives 10 percent off from 100 upwards; "
    "price_of raises KeyError for an unknown name; remove takes the whole line away and raises KeyError when it is not "
    "in the basket. shop.py must go on offering load_prices, price_of and Basket by importing them. Run the checks "
    "with run_checks and finish with a one-line answer."
)
SHOP = '''PRICES = {}


def load_prices(text):
    """Lines "name=price"."""
    for line in text.splitlines():
        name, price = line.split("=")
        PRICES[name.strip()] = float(price)


def price_of(name):
    return PRICES[name]


class Basket:
    def __init__(self):
        self.lines = {}

    def add(self, name, count=1):
        self.lines[name] = self.lines.get(name, 0) + count
'''
PRICES = '''PRICES = {}


def load_prices(text):
    """Lines "name=price"; empty lines are left out."""
    for line in text.splitlines():
        if line.strip():
            name, price = line.split("=")
            PRICES[name.strip()] = float(price)


def price_of(name):
    return PRICES.get(name, 0.0)
'''
# prices.py was written by the other model and is wrong in one point of the request: an unknown name gives 0.0
_TEA = "import prices, basket\nprices.load_prices('tea=4')\nb = basket.Basket()\nb.add('tea', 3)\n"
CHECKS: dict[str, str] = {
    "prices": "import prices\nprices.load_prices('tea=4\\n\\npot=30')\nassert prices.price_of('pot') == 30",
    "basket total": _TEA + "assert b.total() == 12",
    "10 percent from 100": (
        "import prices, basket\nprices.load_prices('pot=50')\nb = basket.Basket()\nb.add('pot')\n"
        "assert b.total() == 50\nb.add('pot')\nassert abs(b.total() - 90) < 1e-9"
    ),
    "remove": (
        _TEA + "b.remove('tea')\nassert b.total() == 0\n"
        "try:\n    b.remove('tea')\nexcept KeyError:\n    pass\nelse:\n    raise SystemExit(1)"
    ),
    "shop still offers all": (
        "import shop, prices, basket\nassert shop.Basket is basket.Basket and shop.price_of is prices.price_of\n"
        "assert shop.load_prices is prices.load_prices"
    ),
    "unknown name": (
        "import prices\ntry:\n    prices.price_of('moon')\nexcept KeyError:\n    pass\nelse:\n    raise SystemExit(1)"
    ),
    "remove gives the count": _TEA + "assert b.remove('tea') == 3",
    "one price list": "import shop\nshop.load_prices('a=1')\nb = shop.Basket()\nb.add('a')\nassert b.total() == 1",
}

SHOWN = ("prices", "basket total", "10 percent from 100", "remove", "shop still offers all")


def _tool(name: str, description: str, **fields: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        parameters={
            "type": "object",
            "properties": {key: {"type": "string", "description": text} for key, text in fields.items()},
            "required": list(fields),
            "additionalProperties": False,
        },
    )


TOOLS = [
    _tool("read_file", "Read a file.", path="the file"),
    _tool("write_file", "Write a whole file.", path="the file", content="its whole content"),
    _tool("run_checks", "Run the checks of the project.", reason="why now"),
]


def _call(number: int, name: str, arguments: dict[str, str]) -> ToolCall:
    return ToolCall(id=f"call_{number}", name=name, raw_arguments=json.dumps(arguments), arguments=arguments)


def started_history() -> list[Message]:
    """What the other model did: it read shop.py and wrote prices.py; basket.py and shop.py are not done."""
    return [
        Message.system("You are a careful programmer. Use the tools; the files are in one folder."),
        Message.user(REQUEST),
        Message(
            role="assistant",
            content="I read the module first.",
            tool_calls=[_call(1, "read_file", {"path": "shop.py"})],
        ),
        Message.tool_result("call_1", SHOP),
        Message(
            role="assistant",
            content="The prices go first.",
            tool_calls=[_call(2, "write_file", {"path": "prices.py", "content": PRICES})],
        ),
        Message.tool_result("call_2", "Written: prices.py"),
        Message(role="assistant", content="prices.py is finished and correct. Next is basket.py."),
        Message.user("One more thing: remove must return how many there were. Go on."),
    ]


def run_check(files: dict[str, str], code: str) -> bool:
    with tempfile.TemporaryDirectory() as folder:
        for name, text in files.items():
            (Path(folder) / name).write_text(text, encoding="utf-8")
        check = Path(folder) / "the_check.py"
        check.write_text(code, encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, str(check)], cwd=folder, capture_output=True, timeout=20, check=False
            )
        except subprocess.TimeoutExpired:
            return False
        return done.returncode == 0


async def play(ask: Callable[[ChatRequest], Awaitable[LLMResponse]], key: str) -> tuple[float, str]:
    files = {"shop.py": SHOP, "prices.py": PRICES}
    history = started_history()
    repeated = bad_calls = steps = 0
    finished = False
    for _ in range(MAX_STEPS):
        steps += 1
        response = await ask(ChatRequest(messages=history, tools=TOOLS))
        history.append(response.to_message(key))
        if not response.tool_calls:
            finished = True
            break
        for call in response.tool_calls:
            arguments: dict[str, Any] = call.arguments or {}
            path = str(arguments.get("path", "")).removeprefix("./")
            if call.name == "read_file" and path in files:
                repeated += files[path] in (SHOP, PRICES)  # it is in the history already
                result = files[path]
            elif (
                call.name == "write_file"
                and path.endswith(".py")
                and "/" not in path
                and "content" in arguments
            ):
                repeated += arguments["content"] == files.get(path)
                files[path] = str(arguments["content"])
                result = f"Written: {path}"
            elif (
                call.name == "run_checks"
            ):  # like a project's own tests: they do not cover everything that was asked
                failed = [n for n, code in CHECKS.items() if n in SHOWN and not run_check(files, code)]
                result = "All checks pass." if not failed else "Failed: " + ", ".join(failed)
            else:
                bad_calls += 1
                result = "Error: no such tool, file or argument."
            history.append(Message.tool_result(call.id, result))
    passed = sum(run_check(files, code) for code in CHECKS.values())
    score = (
        100 * passed / len(CHECKS) - 5 * min(repeated, 4) - 10 * min(bad_calls, 3) - (0 if finished else 10)
    )
    return max(0.0, score), (
        f"{passed} of {len(CHECKS)} checks, {steps} steps, {repeated} repeated, {bad_calls} wrong calls"
        + ("" if finished else ", did not finish")
    )
