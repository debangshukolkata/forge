import pytest

from sales_report import build_report

GOOD = """date,region,product,units,unit_price
2026-01-05,North,Widget,10,2.50
2026-01-20,North,Gadget,2,30
2026-02-01,South,Widget,4,2.5
2026-02-14,North,Widget,1,2.5
"""


def test_totals_and_ordering() -> None:
    report = build_report(GOOD)
    assert set(report) == {
        "rows_ok",
        "skipped",
        "revenue_by_region",
        "revenue_by_month",
        "top_product_by_region",
    }
    assert report["rows_ok"] == 4 and report["skipped"] == []
    assert report["revenue_by_region"] == {"North": 87.5, "South": 10.0}
    assert list(report["revenue_by_region"]) == ["North", "South"]
    assert report["revenue_by_month"] == {"2026-01": 85.0, "2026-02": 12.5}
    assert report["top_product_by_region"] == {"North": "Gadget", "South": "Widget"}


def test_malformed_rows_are_skipped_with_line_numbers() -> None:
    text = (
        "date,region,product,units,unit_price\n"  # 1
        "2026-01-05,North,Widget,10,2.50\n"  # 2 ok
        "2026-13-05,North,Widget,1,1\n"  # 3 bad month
        "2026-02-30,North,Widget,1,1\n"  # 4 not a real date
        "05/01/2026,North,Widget,1,1\n"  # 5 bad format
        "2026-01-06,,Widget,1,1\n"  # 6 empty region
        "2026-01-06,North,,1,1\n"  # 7 empty product
        "2026-01-06,North,Widget,0,1\n"  # 8 zero units
        "2026-01-06,North,Widget,1.5,1\n"  # 9 fractional units
        "2026-01-06,North,Widget,two,1\n"  # 10 text units
        "2026-01-06,North,Widget,1,-1\n"  # 11 negative price
        "2026-01-06,North,Widget,1,1,99\n"  # 12 extra field
        "2026-01-06,North,Widget\n"  # 13 missing fields
        "2026-01-06,North,Widget,1,1,2.5x\n"  # 14 extra field
        "2026-01-07,North,Widget,1,1,0\n"  # 15 extra field
        "2026-01-07,North,Widget,1,1,0,0\n"  # 16 extra fields
        "2026-01-07,North,Widget,1,0\n"  # 17 ok (free item)
    )
    report = build_report(text)
    assert report["rows_ok"] == 2
    assert [line for line, _ in report["skipped"]] == list(range(3, 17))
    assert all(isinstance(reason, str) and reason for _, reason in report["skipped"])
    assert report["revenue_by_region"] == {"North": 25.0}


def test_blank_lines_bom_spaces_and_column_order() -> None:
    text = "﻿ Region , Product,DATE,unit_price, units \n\nNorth , Widget ,2026-03-01, 1.25 , 4 \n\n"
    report = build_report(text)
    assert report["rows_ok"] == 1 and report["skipped"] == []
    assert report["revenue_by_region"] == {"North": 5.0}
    assert report["revenue_by_month"] == {"2026-03": 5.0}


def test_blank_line_still_counts_for_line_numbers() -> None:
    text = "date,region,product,units,unit_price\n\nbad,North,Widget,1,1\n"
    assert [line for line, _ in build_report(text)["skipped"]] == [3]


def test_tie_goes_to_the_alphabetically_first_product() -> None:
    text = "date,region,product,units,unit_price\n2026-01-01,N,Zeta,1,10\n2026-01-01,N,Alpha,2,5\n"
    assert build_report(text)["top_product_by_region"] == {"N": "Alpha"}


def test_rounding_to_two_decimals() -> None:
    text = "date,region,product,units,unit_price\n2026-01-01,N,A,3,0.1\n2026-01-02,N,A,3,0.7\n"
    report = build_report(text)
    assert report["revenue_by_region"] == {"N": 2.4}
    assert report["revenue_by_month"] == {"2026-01": 2.4}


@pytest.mark.parametrize("missing", ["date", "region", "product", "units", "unit_price"])
def test_missing_column_is_named(missing: str) -> None:
    columns = [c for c in ["date", "region", "product", "units", "unit_price"] if c != missing]
    with pytest.raises(ValueError, match=missing):
        build_report(",".join(columns) + "\n")


def test_header_only_and_empty_text() -> None:
    report = build_report("date,region,product,units,unit_price\n")
    assert report == {
        "rows_ok": 0,
        "skipped": [],
        "revenue_by_region": {},
        "revenue_by_month": {},
        "top_product_by_region": {},
    }
    with pytest.raises(ValueError):
        build_report("")


def test_quoted_fields_with_commas() -> None:
    text = 'date,region,product,units,unit_price\n2026-01-01,North,"Widget, large",2,5\n'
    assert build_report(text)["top_product_by_region"] == {"North": "Widget, large"}
