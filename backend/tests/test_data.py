"""Source-quality fixtures exercise each exclusion and invoice aggregation."""

import pandas as pd
import pytest
from src.data_loader import clean_retail, catalog_from_events


def source_row(**updates):
    row = dict(
        InvoiceNo="536365",
        StockCode="85123A",
        Description="WHITE HOLDER",
        Quantity=2,
        InvoiceDate="2011-01-01",
        UnitPrice=2.5,
        CustomerID=17850.0,
        Country="United Kingdom",
    )
    return row | updates


def test_cleaning_audit_and_repeated_invoice_lines():
    raw = pd.DataFrame(
        [
            source_row(),
            source_row(),
            source_row(Quantity=3),
            source_row(CustomerID=None),
            source_row(InvoiceNo="c123"),
            source_row(Quantity=-1),
            source_row(UnitPrice=0),
            source_row(InvoiceDate="bad"),
            source_row(StockCode="POST"),
            source_row(Description=" "),
        ]
    )
    events, report = clean_retail(raw)
    assert len(events) == 1
    assert events.iloc[0].user_id == "17850"
    assert events.iloc[0].quantity == 5
    assert events.iloc[0].interaction_score == 1
    assert report["exact_duplicate_lines"] == 1
    assert report["merged_invoice_product_lines"] == 1
    removed = sum(
        value
        for key, value in report.items()
        if key not in {"raw_rows", "purchase_events", "users", "products"}
    )
    assert removed + report["purchase_events"] == report["raw_rows"]
    assert catalog_from_events(events).iloc[0].category is None


def test_empty_cleaned_data_and_bad_schema_fail():
    with pytest.raises(ValueError, match="No valid purchases"):
        clean_retail(pd.DataFrame([source_row(Quantity=0)]))
    with pytest.raises(ValueError, match="Missing source"):
        clean_retail(pd.DataFrame())
