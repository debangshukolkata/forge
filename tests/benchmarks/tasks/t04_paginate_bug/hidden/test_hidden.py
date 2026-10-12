import pytest

from paginate import paginate

ITEMS = list(range(1, 11))  # 10 items


def test_pages_of_four() -> None:
    first = paginate(ITEMS, 1, 4)
    assert first["items"] == [1, 2, 3, 4]
    assert (first["total_pages"], first["has_next"], first["has_prev"]) == (3, True, False)
    middle = paginate(ITEMS, 2, 4)
    assert middle["items"] == [5, 6, 7, 8]
    assert (middle["has_next"], middle["has_prev"]) == (True, True)
    last = paginate(ITEMS, 3, 4)
    assert last["items"] == [9, 10]
    assert (last["has_next"], last["has_prev"]) == (False, True)


def test_metadata_is_complete() -> None:
    result = paginate(ITEMS, 2, 4)
    assert result["page"] == 2 and result["per_page"] == 4 and result["total_items"] == 10
    assert set(result) == {"items", "page", "per_page", "total_items", "total_pages", "has_next", "has_prev"}


def test_exact_multiple_has_no_extra_page() -> None:
    result = paginate(list(range(8)), 2, 4)
    assert result["total_pages"] == 2
    assert result["items"] == [4, 5, 6, 7]
    assert result["has_next"] is False


def test_page_beyond_the_last_is_empty() -> None:
    result = paginate(ITEMS, 9, 4)
    assert result["items"] == [] and result["has_next"] is False and result["has_prev"] is True


def test_empty_list() -> None:
    result = paginate([], 1, 5)
    assert result["items"] == [] and result["total_pages"] == 0
    assert result["has_next"] is False and result["has_prev"] is False


def test_single_big_page() -> None:
    result = paginate(ITEMS, 1, 100)
    assert result["items"] == ITEMS and result["total_pages"] == 1 and result["has_next"] is False


@pytest.mark.parametrize(("page", "per_page"), [(0, 5), (-1, 5), (1, 0), (1, -3)])
def test_invalid_numbers(page: int, per_page: int) -> None:
    with pytest.raises(ValueError):
        paginate(ITEMS, page, per_page)


def test_does_not_change_the_input() -> None:
    items = list(ITEMS)
    paginate(items, 2, 3)
    assert items == ITEMS
