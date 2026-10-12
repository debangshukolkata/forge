import csv
import io
from collections import defaultdict
from datetime import datetime
from typing import Any

REQUIRED = ["date", "region", "product", "units", "unit_price"]


def build_report(csv_text: str) -> dict[str, Any]:
    reader = csv.reader(io.StringIO(csv_text.lstrip("﻿")))
    rows = list(enumerate(reader, start=1))
    if not rows:
        raise ValueError("the CSV has no header")
    header = [name.strip().lower() for name in rows[0][1]]
    for column in REQUIRED:
        if column not in header:
            raise ValueError(f"missing column: {column}")
    position = {name: header.index(name) for name in REQUIRED}
    by_region: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    by_product: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    skipped: list[tuple[int, str]] = []
    ok = 0
    for line_number, fields in rows[1:]:
        if not fields or all(not field.strip() for field in fields):
            continue
        if len(fields) != len(header):
            skipped.append((line_number, f"expected {len(header)} fields, got {len(fields)}"))
            continue
        values = {name: fields[position[name]].strip() for name in REQUIRED}
        try:
            when = datetime.strptime(values["date"], "%Y-%m-%d")
            if len(values["date"]) != 10:
                raise ValueError("date must be YYYY-MM-DD")
        except ValueError:
            skipped.append((line_number, f"invalid date {values['date']!r}"))
            continue
        if not values["region"] or not values["product"]:
            skipped.append((line_number, "region or product is empty"))
            continue
        if not values["units"].isdigit() or int(values["units"]) < 1:
            skipped.append(
                (line_number, f"units must be a whole number of at least 1, got {values['units']!r}")
            )
            continue
        try:
            price = float(values["unit_price"])
        except ValueError:
            skipped.append((line_number, f"unit_price is not a number: {values['unit_price']!r}"))
            continue
        if price < 0 or price != price:
            skipped.append((line_number, "unit_price cannot be negative"))
            continue
        revenue = int(values["units"]) * price
        by_region[values["region"]] += revenue
        by_month[when.strftime("%Y-%m")] += revenue
        by_product[values["region"]][values["product"]] += revenue
        ok += 1
    return {
        "rows_ok": ok,
        "skipped": skipped,
        "revenue_by_region": {k: round(by_region[k], 2) for k in sorted(by_region)},
        "revenue_by_month": {k: round(by_month[k], 2) for k in sorted(by_month)},
        "top_product_by_region": {
            region: min(products, key=lambda name: (-round(products[name], 6), name))
            for region, products in sorted(by_product.items())
        },
    }
