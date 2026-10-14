from orders import Order
from report import monthly_counts, monthly_total_cents

ORDERS = [
    Order(1, "2026-03-10T06:00:00+00:00", 10_00),
    Order(2, "2026-03-20T12:00:00+00:00", 25_50),
    Order(3, "2026-04-02T09:00:00+00:00", 40_00),
]


def test_a_month_in_the_middle_is_summed() -> None:
    assert monthly_total_cents(ORDERS, 2026, 3) == 35_50


def test_counts_per_month() -> None:
    assert monthly_counts(ORDERS) == {(2026, 3): 2, (2026, 4): 1}
