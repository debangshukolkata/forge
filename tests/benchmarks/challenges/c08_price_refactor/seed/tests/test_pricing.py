from pricing import Customer, Line, price_order


def test_a_standard_customer_in_germany() -> None:
    assert price_order([Line(1_000, 2)], Customer()) == 2_380


def test_an_empty_order_costs_nothing() -> None:
    assert price_order([], Customer("gold")) == 0
