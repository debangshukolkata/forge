Create a module `sales_report.py` with `build_report(csv_text: str) -> dict` that turns a sales CSV into a summary.

Input columns (header on line 1, any column order, header names compared ignoring case and surrounding spaces): `date,region,product,units,unit_price`.

Rules for each data row (line numbers are 1-based and count the header as line 1):
- A leading byte-order mark (BOM) on the text is ignored. Fields are trimmed of surrounding spaces. A completely blank line is ignored and is not an error.
- A row is valid when: the date is a real calendar date written `YYYY-MM-DD`; region and product are not empty; `units` is a whole number of at least 1; `unit_price` is a number of at least 0 (a decimal point, not a comma). Otherwise the row is skipped and recorded in `skipped` as `(line_number, reason)` where `reason` is a short non-empty text. A row with the wrong number of fields is skipped too.
- If a required column is missing from the header, raise `ValueError` naming the missing column. Text with no header at all also raises `ValueError`.

The result dictionary has exactly these keys:
- `rows_ok`: number of valid rows.
- `skipped`: list of `(line_number, reason)` in file order.
- `revenue_by_region`: `{region: total}` where revenue is units * unit_price summed, rounded to 2 decimals.
- `revenue_by_month`: `{"YYYY-MM": total}`, rounded to 2 decimals.
- `top_product_by_region`: `{region: product}` with the highest total revenue in that region (a tie goes to the product that comes first alphabetically).

Dictionaries are ordered alphabetically by key. Write tests for it too. Use only the standard library.
