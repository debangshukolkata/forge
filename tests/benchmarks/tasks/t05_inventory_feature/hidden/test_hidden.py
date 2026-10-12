import csv
import io

import pytest

from inventory import Inventory


def stocked() -> Inventory:
    inventory = Inventory()
    inventory.add("C3", "Washer", 0)
    inventory.add("A1", "Bolt", 12)
    inventory.add("B2", "Nut", 5)
    inventory.add("D4", "Anchor", 5)
    inventory.add("E5", "Screw", 100)
    return inventory


def test_existing_behaviour_is_kept() -> None:
    inventory = stocked()
    inventory.remove("A1", 2)
    assert inventory.quantity("A1") == 10
    assert [item.sku for item in inventory.items()] == ["A1", "B2", "C3", "D4", "E5"]
    assert inventory.quantity("nope") == 0


def test_low_stock_report_filters_and_orders() -> None:
    assert stocked().low_stock_report() == [("Washer", 0), ("Anchor", 5), ("Nut", 5)]


def test_low_stock_report_threshold() -> None:
    assert stocked().low_stock_report(threshold=0) == [("Washer", 0)]
    assert [name for name, _ in stocked().low_stock_report(threshold=12)] == [
        "Washer",
        "Anchor",
        "Nut",
        "Bolt",
    ]
    assert stocked().low_stock_report(threshold=1000)[-1] == ("Screw", 100)


def test_low_stock_report_empty_and_invalid() -> None:
    assert Inventory().low_stock_report() == []
    with pytest.raises(ValueError):
        stocked().low_stock_report(threshold=-1)


def test_to_csv_layout() -> None:
    text = stocked().to_csv()
    assert text.startswith("sku,name,quantity\n")
    assert text.endswith("\n") and "\r" not in text
    assert text.splitlines()[1:3] == ["A1,Bolt,12", "B2,Nut,5"]


def test_to_csv_quotes_awkward_names_and_round_trips() -> None:
    inventory = Inventory()
    inventory.add("X1", 'Bolt, "heavy"', 3)
    inventory.add("X2", "Line\nbreak", 1)
    rows = list(csv.reader(io.StringIO(inventory.to_csv(), newline="")))
    assert rows == [["sku", "name", "quantity"], ["X1", 'Bolt, "heavy"', "3"], ["X2", "Line\nbreak", "1"]]


def test_to_csv_of_empty_inventory_is_only_the_header() -> None:
    assert Inventory().to_csv() == "sku,name,quantity\n"
