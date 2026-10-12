import pytest

from billing import invoice_total_member, invoice_total_retail, invoice_total_wholesale

LINES = [(10.0, 2), (5.0, 1)]


def test_retail() -> None:
    assert invoice_total_retail(LINES) == 30.0


def test_wholesale_small_order() -> None:
    assert invoice_total_wholesale(LINES) == 28.5


def test_member() -> None:
    assert invoice_total_member(LINES) == 27.0


def test_negative_quantity_is_rejected() -> None:
    with pytest.raises(ValueError):
        invoice_total_retail([(1.0, -1)])
