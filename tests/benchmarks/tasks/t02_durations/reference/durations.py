import re

UNITS = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
PART = re.compile(r"(\d+)([dhms])", re.IGNORECASE)


def parse_duration(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty duration")
    position = 0
    total = 0
    last_rank = -1
    order = "dhms"
    while position < len(stripped):
        match = PART.match(stripped, position)
        if match is None:
            raise ValueError(f"cannot read a duration part at {stripped[position:]!r}")
        unit = match.group(2).lower()
        rank = order.index(unit)
        if rank <= last_rank:
            raise ValueError(f"unit {unit!r} is repeated or out of order")
        last_rank = rank
        total += int(match.group(1)) * dict(UNITS)[unit]
        position = match.end()
        while position < len(stripped) and stripped[position] == " ":
            position += 1
    return total


def format_duration(seconds: int) -> str:
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
        raise ValueError("seconds must be a non-negative integer")
    if seconds == 0:
        return "0s"
    parts = []
    for unit, size in UNITS:
        count, seconds = divmod(seconds, size)
        if count:
            parts.append(f"{count}{unit}")
    return "".join(parts)
