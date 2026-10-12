Add two features to the existing `Inventory` class in `inventory.py` (leave the current behaviour as it is):

1. `low_stock_report(threshold: int = 5) -> list[tuple[str, int]]` returns `(name, quantity)` pairs for every item whose quantity is at or below `threshold`, sorted by quantity ascending and then by name. A negative threshold raises `ValueError`.
2. `to_csv() -> str` returns the whole inventory as CSV text with the header `sku,name,quantity`, one row per item sorted by sku, lines ended with `\n` (also after the last row). Names containing commas, quotes or line breaks must be quoted correctly so that Python's `csv` module reads the text back to the same values.

Add tests for both next to the existing ones. Keep the existing tests passing. Use only the standard library.
