from decimal import ROUND_HALF_UP, Decimal

import pytest

from shop.pricing import order_total

# The shop's rule: the discount comes off the subtotal first, tax is charged on the discounted amount,
# and the result is rounded half up to whole cents (not half to even).


def expected(lines, discount):
    subtotal = sum(Decimal(str(p)) * q for p, q in lines)
    discounted = subtotal * (Decimal(100) - Decimal(str(discount))) / Decimal(100)
    total = discounted * Decimal("1.18")
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def test_no_discount():
    assert order_total([(10.0, 2), (4.5, 1)]) == expected([(10.0, 2), (4.5, 1)], 0)


def test_discount_before_tax():
    assert order_total([(100.0, 1)], 10) == 106.2


def test_half_cents_round_up():
    assert order_total([(0.25, 1)], 0) == 0.30
    assert order_total([(1.25, 1)], 0) == 1.48
    assert order_total([(2.5, 1)], 50) == 1.48


def test_many_lines_with_discount():
    lines = [(19.99, 3), (5.49, 7), (0.99, 12)]
    assert order_total(lines, 15) == expected(lines, 15)


def test_empty_order_is_zero():
    assert order_total([]) == 0.0


def test_negative_quantity_is_rejected():
    with pytest.raises(ValueError):
        order_total([(10.0, -1)])
