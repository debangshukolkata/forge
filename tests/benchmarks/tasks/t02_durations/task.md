Create a Python module `durations.py` with two functions.

`parse_duration(text: str) -> int` turns text such as "1h30m" into whole seconds.
- Units: `d` (86400 seconds), `h` (3600), `m` (60), `s` (1), upper or lower case.
- A duration is one or more `<integer><unit>` parts, each unit at most once, always in the order d, h, m, s. Spaces between parts and around the whole text are allowed ("1h 30m", " 2d ").
- Anything else raises `ValueError` with a helpful message: an empty string, a number with no unit ("5"), a decimal ("1.5h"), a negative number, an unknown unit, a repeated unit ("1h1h"), parts in the wrong order ("30m1h").
- A `text` that is not a string raises `TypeError`.

`format_duration(seconds: int) -> str` is the reverse: it writes the shortest exact form using d, h, m, s with no spaces and no zero parts ("5400" becomes "1h30m", "90061" becomes "1d1h1m1s", "0" becomes "0s"). A negative or non-integer input raises `ValueError`.

Parsing the output of `format_duration` must always give back the original number.

Write tests for it too. Use only the standard library.
