import ast
from pathlib import Path

import pytest

import billing
from billing import calculate_total, invoice_total_member, invoice_total_retail, invoice_total_wholesale

SMALL = [(10.0, 2), (5.0, 1)]
BIG = [(100.0, 10)]
MIXED = [(19.99, 3), (4.5, 12), (0.0, 7)]


@pytest.mark.parametrize(
    ("function", "kind"),
    [
        (invoice_total_retail, "retail"),
        (invoice_total_wholesale, "wholesale"),
        (invoice_total_member, "member"),
    ],
)
@pytest.mark.parametrize("lines", [SMALL, BIG, MIXED, []])
def test_wrappers_equal_calculate_total(function, kind, lines) -> None:  # type: ignore[no-untyped-def]
    assert function(lines) == calculate_total(lines, kind)


def test_known_values() -> None:
    assert invoice_total_retail(SMALL) == 30.0
    assert invoice_total_wholesale(SMALL) == 28.5
    assert invoice_total_member(SMALL) == 27.0
    assert invoice_total_wholesale(BIG) == 1020.0  # subtotal 1000 reaches the 15 % rate
    assert invoice_total_member(BIG) == 1080.0
    assert invoice_total_retail(MIXED) == round((19.99 * 3 + 4.5 * 12) * 1.2, 2)
    assert invoice_total_retail([]) == 0.0


def test_unknown_customer_type() -> None:
    with pytest.raises(ValueError):
        calculate_total(SMALL, "vip")


@pytest.mark.parametrize("lines", [[(1.0, -1)], [(-1.0, 1)]])
@pytest.mark.parametrize("kind", ["retail", "wholesale", "member"])
def test_negative_values_rejected(lines, kind) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        calculate_total(lines, kind)


def test_wrappers_are_thin_and_the_logic_is_not_repeated() -> None:
    tree = ast.parse(Path(billing.__file__).read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ("invoice_total_retail", "invoice_total_wholesale", "invoice_total_member"):
        body = [
            statement
            for statement in functions[name].body
            if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
        ]
        assert len(body) <= 3, f"{name} has {len(body)} statements"
    source = Path(billing.__file__).read_text(encoding="utf-8")
    assert source.count("negative price or quantity") == 1
    assert source.count("TAX_RATE") <= 3 and source.count("0.2") <= 1
