from shop.orders import describe, mark_paid


def test_describe_uses_the_money_format(sample_orders) -> None:
    assert describe(sample_orders[0]) == "#1 Asha: 123.45 EUR (paid)"


def test_a_cancelled_order_cannot_be_paid(sample_orders) -> None:
    result = mark_paid(sample_orders[2])
    assert not result.ok and "cancelled" in (result.error or "")
    assert mark_paid(sample_orders[1]).value.status == "paid"
