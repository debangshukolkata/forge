import pytest

from inventory import Inventory


def test_add_and_remove() -> None:
    inventory = Inventory()
    inventory.add("A1", "Bolt", 10)
    inventory.add("A1", "Bolt", 5)
    assert inventory.quantity("A1") == 15
    inventory.remove("A1", 6)
    assert inventory.quantity("A1") == 9


def test_remove_more_than_in_stock() -> None:
    inventory = Inventory()
    inventory.add("A1", "Bolt", 2)
    with pytest.raises(ValueError):
        inventory.remove("A1", 3)
