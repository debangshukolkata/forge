from __future__ import annotations

import pytest

from catalog import Catalog
from members import MemberRegistry


def test_catalog_add_get_all() -> None:
    catalog = Catalog()
    catalog.add("B2", "Dune", 2)
    catalog.add("B1", "Emma")
    assert [book.id for book in catalog.all()] == ["B1", "B2"]
    assert catalog.get("B2").copies == 2
    with pytest.raises(KeyError):
        catalog.get("B9")
    with pytest.raises(ValueError):
        catalog.add("B1", "Again")
    with pytest.raises(ValueError):
        catalog.add("B3", "None", 0)


def test_members() -> None:
    members = MemberRegistry()
    members.add("M1", "Ana")
    assert members.get("M1").name == "Ana"
    with pytest.raises(KeyError):
        members.get("M2")
    with pytest.raises(ValueError):
        members.add("M1", "Other")
