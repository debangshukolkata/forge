from db import connect
from products import add_product, get_product


def test_a_product_can_be_added_and_read() -> None:
    connection = connect()
    product_id = add_product(connection, "Brass lamp", 4_500, "2026-01-05")
    assert get_product(connection, product_id)["name"] == "Brass lamp"
