Create a Python module `textutil.py` with one function:

`slugify(text: str, max_length: int | None = None) -> str`

Rules:
- Accented letters become their plain ASCII letter (for example "é" becomes "e").
- The result is lowercase and uses only `a-z`, `0-9` and single hyphens. Every run of other characters becomes one hyphen. No hyphen at the start or the end.
- If the result would be empty, return an empty string.
- `max_length`, when given, caps the length of the result. Cut at a word boundary (a hyphen) so no word is chopped in the middle, and never end with a hyphen. If the very first word is longer than `max_length`, cut that word at `max_length`.
- `max_length` below 1 raises `ValueError`. A `text` that is not a string raises `TypeError`.

Write tests for it too. Use only the standard library.
