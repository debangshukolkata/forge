import pytest

from textutil import slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello World", "hello-world"),
        ("  Héllo,   Wörld!  ", "hello-world"),
        ("Crème brûlée à la façon", "creme-brulee-a-la-facon"),
        ("a--b__c  d", "a-b-c-d"),
        ("---", ""),
        ("", ""),
        ("Python 3.13 released", "python-3-13-released"),
        ("ALREADY-slugged", "already-slugged"),
    ],
)
def test_basic_rules(text: str, expected: str) -> None:
    assert slugify(text) == expected


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("one two three four", 7, "one-two"),
        ("one two three four", 8, "one-two"),
        ("one two three four", 9, "one-two"),
        ("one two three four", 13, "one-two-three"),
        ("one two three four", 100, "one-two-three-four"),
        ("one two three four", 3, "one"),
        ("abcdefghij klm", 5, "abcde"),
        ("short", 5, "short"),
    ],
)
def test_max_length_cuts_at_word_boundaries(text: str, limit: int, expected: str) -> None:
    result = slugify(text, max_length=limit)
    assert result == expected
    assert len(result) <= limit
    assert not result.endswith("-")


def test_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        slugify("abc", max_length=0)
    with pytest.raises(TypeError):
        slugify(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        slugify(None)  # type: ignore[arg-type]
