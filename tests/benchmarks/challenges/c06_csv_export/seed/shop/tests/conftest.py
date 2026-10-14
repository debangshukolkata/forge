import pytest
from shop.orders import Order


@pytest.fixture
def sample_orders() -> list[Order]:
    return [
        Order(1, "Asha", 12_345, "paid"),
        Order(2, "Bo, the Baker", 999, "open"),
        Order(3, "Chen", -500, "cancelled"),
    ]
