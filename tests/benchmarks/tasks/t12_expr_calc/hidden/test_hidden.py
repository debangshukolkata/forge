from __future__ import annotations

import pytest

from calc import CalcError, evaluate


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("10 - 4 - 3", 3),
        ("2 ** 3 ** 2", 512),
        ("-2 ** 2", -4),
        ("2 ** -1", 0.5),
        ("2 ** -2 ** 2", 0.0625),
        ("- - 3", 3),
        ("+5", 5),
        ("6 / 3", 2.0),
        ("7 // 2", 3),
        ("-7 // 2", -4),
        ("-7 % 3", 2),
        ("7.5 % 2", 1.5),
        ("1e3", 1000.0),
        ("2.5E-2", 0.025),
        (".5 + 5.", 5.5),
        ("  4  *  ( 2 + 1 )  ", 12),
        ("2 * -3", -6),
        ("10 / 4 * 2", 5.0),
        ("2 ** 10", 1024),
        ("min(3, 1, 2)", 1),
        ("max(1)", 1),
        ("abs(-4.5)", 4.5),
        ("sqrt(16)", 4.0),
        ("round(2.5)", 2),
        ("round(3.14159, 2)", 3.14),
        ("max(1, min(5, 3) + 1) * 2", 8),
        ("abs(min(-1, -2)) ** 2", 4),
    ],
)
def test_values(text: str, expected: float) -> None:
    result = evaluate(text)
    assert result == pytest.approx(expected)


def test_integers_stay_integers_and_floats_stay_floats() -> None:
    assert type(evaluate("2 + 3")) is int
    assert type(evaluate("2 * 3")) is int
    assert type(evaluate("6 / 3")) is float
    assert type(evaluate("1e2")) is float
    assert type(evaluate("2 ** 3")) is int
    assert type(evaluate("2 ** -1")) is float
    assert type(evaluate("round(2.7)")) is int


def test_variables() -> None:
    assert evaluate("x * 2 + y", {"x": 4, "y": 0.5}) == 8.5
    assert evaluate("max(a, b)", {"a": 3, "b": 9}) == 9


def test_big_integers_are_exact() -> None:
    assert evaluate("2 ** 100") == 2**100


@pytest.mark.parametrize(
    "text,position",
    [
        ("", 0),
        ("   ", 3),
        ("1 +", 3),
        ("1 + * 2", 4),
        ("(1 + 2", 6),
        ("1 + 2)", 5),
        ("1 $ 2", 2),
        ("2(3)", 1),
        ("2 3", 2),
        ("1 / 0", 2),
        ("5 // 0", 2),
        ("5 % (3 - 3)", 2),
        ("1 + 2 / (4 - 4)", 6),
        ("0 ** -1", 2),
        ("foo + 1", 0),
        ("1 + bar", 4),
        ("foo(1)", 0),
        ("1 + nope(2)", 4),
        ("abs()", 0),
        ("abs(1, 2)", 0),
        ("min()", 0),
        ("round(1, 2, 3)", 0),
        ("sqrt(-1)", 0),
        ("2 * sqrt(1 - 2)", 4),
        ("10.0 ** 1000", 5),
        ("max(1, 2", 8),
        ("max(1 2)", 6),
        ("x(2)", 0),
    ],
)
def test_errors_have_positions(text: str, position: int) -> None:
    with pytest.raises(CalcError) as caught:
        evaluate(text, {"x": 1})
    assert caught.value.position == position
    assert caught.value.message
    assert str(caught.value) == f"{caught.value.message} at position {position}"


def test_calc_error_is_a_value_error() -> None:
    assert issubclass(CalcError, ValueError)


@pytest.mark.parametrize("text", ["__import__('os')", "1 ; 2", "'a' + 'b'", "x.y", "1 if 2 else 3", "[1]"])
def test_python_syntax_is_not_accepted(text: str) -> None:
    with pytest.raises(CalcError):
        evaluate(text, {"x": 1})


def test_no_other_exception_types_escape() -> None:
    for text in ["1 / 0", "2 ** 10000000000.5", "(-8) ** 0.5", "0.0 ** -1", "10 ** 400 / 1"]:
        try:
            evaluate(text)
        except CalcError:
            pass
        except Exception as error:  # pragma: no cover - the point of the test
            pytest.fail(f"{text!r} raised {type(error).__name__}")


def test_eval_is_not_used() -> None:
    import ast
    import inspect

    import calc

    for node in ast.walk(ast.parse(inspect.getsource(calc))):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            owner = getattr(getattr(node.func, "value", None), "id", "")
            assert name not in ("eval", "exec", "literal_eval") and not (name == "compile" and owner != "re")
