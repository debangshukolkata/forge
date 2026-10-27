---
id: rcp-data-pandas-polars
type: recipe
title: Tables with pandas and Polars
summary: "Loading with explicit dtypes, vectorised work, groupby, joins, missing values, big files, input validation and pandas pitfalls."
moods: [robust, clean]
products: [data analysis, report, etl script]
tags: [pandas, polars, dataframe, groupby, join, lazy, validation]
density: any
dependencies: [pandas, polars]
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: not executed (pandas and polars are not installed in the build venv); follows the documented pandas 2 and Polars 1 APIs
---

## Tables with pandas and Polars

Rules:
- Choose Polars for big files, speed and a strict, readable API; pandas when the rest of the stack or a library needs it.
  Convert at the border (`pl.from_pandas`, `df.to_pandas()`), not back and forth in the middle.
- Never trust the inferred types. Pass dtypes and date columns when reading, and keep ids as strings (leading zeros!).
- Validate input right after loading: required columns present, no duplicate keys, values in range. Fail with a message
  naming the column and the first bad rows; do not let a bad file produce a plausible wrong report.
- Think in columns. A loop over rows or `df.apply(axis=1)` is 10-100 times slower than a vectorised expression.
- Be explicit about missing values: count them, then decide to drop, fill or keep, and write down why. `NaN` in pandas
  and `null` in Polars are not equal to anything, including themselves.
- Joins: state the expected cardinality and check it (`validate="m:1"` in pandas, `join(..., validate="m:1")` in Polars);
  a many-to-many join silently multiplies rows and totals.
- Files larger than memory: `pl.scan_csv(...)` / `scan_parquet` (lazy, filters and column choice pushed down) and
  `.collect()` at the end; in pandas read `chunksize=` and aggregate per chunk. Prefer Parquet over CSV for anything you re-read.
- Money is `Decimal` or integer cents, not float.

Worked example (revenue per region, the same job in both libraries):

```python
import pandas as pd
import polars as pl

SCHEMA = {"order_id": "string", "region": "string", "units": "Int64", "price": "float64"}


def load_orders_pandas(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=SCHEMA, parse_dates=["ordered_at"])
    missing = {"order_id", "region", "units", "price", "ordered_at"} - set(df.columns)
    if missing:
        raise ValueError(f"orders file lacks columns: {sorted(missing)}")
    if df["order_id"].duplicated().any():
        raise ValueError(
            f"duplicate order ids, first: {df.loc[df['order_id'].duplicated(), 'order_id'].iloc[0]}"
        )
    return df


def revenue_pandas(orders: pd.DataFrame, regions: pd.DataFrame) -> pd.DataFrame:
    orders = orders.assign(revenue=orders["units"] * orders["price"])  # vectorised
    orders = orders.dropna(subset=["units", "price"])  # decision: unpriced rows are excluded
    merged = orders.merge(regions, on="region", how="left", validate="m:1")  # regions has one row per code
    return (
        merged.groupby("region_name", dropna=False, as_index=False)
        .agg(orders=("order_id", "count"), revenue=("revenue", "sum"))
        .sort_values("revenue", ascending=False)
    )


def revenue_polars(path: str, regions: pl.DataFrame) -> pl.DataFrame:
    return (
        pl.scan_csv(path, schema_overrides={"order_id": pl.String, "region": pl.String})
        .drop_nulls(["units", "price"])
        .with_columns((pl.col("units") * pl.col("price")).alias("revenue"))
        .join(regions.lazy(), on="region", how="left", validate="m:1")
        .group_by("region_name")
        .agg(pl.len().alias("orders"), pl.col("revenue").sum())
        .sort("revenue", descending=True)
        .collect()
    )
```

Pandas pitfalls worth a test each:
- Chained assignment (`df[df.a > 1]["b"] = 0`) changes a copy and does nothing; write `df.loc[df.a > 1, "b"] = 0`,
  or build a new frame with `assign`. Turn on copy-on-write (`pd.options.mode.copy_on_write = True`).
- `groupby` drops rows whose key is null unless `dropna=False`.
- `merge` on columns of different dtypes (int vs string) raises or matches nothing; align types first.
- `df.apply(lambda row: ...)` on a big frame is the usual reason a script takes an hour.
- `SettingWithCopyWarning` is a bug report, not noise.

Gotchas:
- Dates: parse with an explicit format and a timezone; mixed formats silently become strings.
- `float` sums differ by order; compare with a tolerance (`math.isclose`) in tests and round only for display.
- Test with a tiny frame built inline, including a null, a duplicate key and an empty frame.
