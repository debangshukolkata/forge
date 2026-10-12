from paginate import paginate


def test_first_page_has_the_first_items() -> None:
    result = paginate(list(range(1, 11)), page=1, per_page=4)
    assert result["items"] == [1, 2, 3, 4]
