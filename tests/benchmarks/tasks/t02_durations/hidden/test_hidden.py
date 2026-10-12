import pytest

from durations import format_duration, parse_duration


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("1h30m", 5400),
        ("2d", 172800),
        ("90s", 90),
        ("1D2H3M4S", 93784),
        (" 1h 30m ", 5400),
        ("0s", 0),
        ("1d 1s", 86401),
    ],
)
def test_parse_valid(text: str, seconds: int) -> None:
    assert parse_duration(text) == seconds
    assert isinstance(parse_duration(text), int)


@pytest.mark.parametrize(
    "text", ["", "   ", "5", "1.5h", "-1h", "1x", "1h1h", "30m1h", "h", "1h-30m", "1 h", "1h30"]
)
def test_parse_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)


def test_parse_wrong_type() -> None:
    with pytest.raises(TypeError):
        parse_duration(90)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0s"), (59, "59s"), (60, "1m"), (5400, "1h30m"), (90061, "1d1h1m1s"), (86400, "1d"), (3601, "1h1s")],
)
def test_format(seconds: int, text: str) -> None:
    assert format_duration(seconds) == text


@pytest.mark.parametrize("value", [-1, 1.5, "10", None])
def test_format_invalid(value: object) -> None:
    with pytest.raises(ValueError):
        format_duration(value)  # type: ignore[arg-type]


def test_round_trip() -> None:
    for seconds in [0, 1, 59, 60, 61, 3599, 3600, 86399, 86400, 123456, 10**7 + 13]:
        assert parse_duration(format_duration(seconds)) == seconds
