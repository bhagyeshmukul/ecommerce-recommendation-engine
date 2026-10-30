"""Download UCI purchases and produce a deterministic, audited training snapshot.

The source contains purchase lines, not clicks, ratings, or an engagement experiment.
Keep raw data immutable; every cleaning rule is counted in the quality report.
"""

from __future__ import annotations

import hashlib
import io
import time
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/352/online-retail"
EXPECTED_RAW_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
PIPELINE_VERSION = "uci-purchases-v1"
SOURCE_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]


def sha256_file(path: Path) -> str:
    """Hash bytes rather than modification times so moved files retain identity."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download_source(data_dir: Path = DATA_DIR) -> Path:
    """Cache the official workbook; interrupted downloads never become valid caches."""
    destination = data_dir / "raw" / "online_retail.xlsx"
    if destination.exists():
        if sha256_file(destination) != EXPECTED_RAW_SHA256:
            raise ValueError(
                "Cached workbook differs from the pinned UCI source. Restore the original Online Retail.xlsx."
            )
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            response = httpx.get(SOURCE_URL, follow_redirects=True, timeout=120)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                member = next(
                    name
                    for name in archive.namelist()
                    if name.endswith("Online Retail.xlsx")
                )
                if archive.getinfo(member).file_size > 40_000_000:
                    raise ValueError("Unexpected workbook size from UCI")
                workbook = archive.read(member)
            temporary = destination.with_suffix(".partial")
            temporary.write_bytes(workbook)
            if sha256_file(temporary) != EXPECTED_RAW_SHA256:
                raise ValueError(
                    "Downloaded workbook differs from the pinned UCI source"
                )
            temporary.replace(destination)
            return destination
        except (httpx.HTTPError, zipfile.BadZipFile, StopIteration):
            if attempt == 2:
                raise RuntimeError(
                    f"UCI download failed. Retry, or place the workbook at {destination}"
                ) from None
            time.sleep(attempt + 1)
    raise AssertionError("Unreachable")


def clean_retail(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep positive, identifiable merchandise purchases; aggregate invoice lines.

    Rules are sequential, so removal counts add up rather than double-count rows.
    Quantity is retained for history only, never used as preference strength.
    """
    missing = set(SOURCE_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing source columns: {sorted(missing)}")
    frame = raw[SOURCE_COLUMNS].copy()
    counts = {"raw_rows": len(frame)}

    def remove(mask: pd.Series, reason: str) -> None:
        nonlocal frame
        mask = mask.fillna(True)
        counts[reason] = int(mask.sum())
        frame = frame.loc[~mask].copy()

    remove(
        frame[["CustomerID", "StockCode", "InvoiceNo", "Description"]]
        .isna()
        .any(axis=1),
        "missing_identifiers_or_description",
    )
    for column in ["InvoiceNo", "StockCode", "Description", "CustomerID"]:
        frame[column] = frame[column].astype("string").str.strip()
    # Excel numeric customer IDs can arrive as 12345.0; preserve stable string keys.
    frame["CustomerID"] = frame["CustomerID"].str.replace(r"\.0$", "", regex=True)
    frame["StockCode"] = frame["StockCode"].str.upper()
    remove(
        frame[["CustomerID", "InvoiceNo", "StockCode", "Description"]]
        .eq("")
        .any(axis=1),
        "blank_identifiers_or_description",
    )
    frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"], errors="coerce")
    remove(frame["InvoiceDate"].isna(), "invalid_dates")
    remove(frame["InvoiceNo"].str.upper().str.startswith("C"), "cancelled_lines")
    for column in ["Quantity", "UnitPrice"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    remove(
        ~(
            frame["Quantity"].gt(0)
            & frame["UnitPrice"].gt(0)
            & np.isfinite(frame["Quantity"])
            & np.isfinite(frame["UnitPrice"])
        ),
        "nonpositive_or_invalid_quantity_price",
    )
    # Merchandise codes are five digits with an optional letter suffix. This
    # excludes POST, DOT, discounts, bank charges, manual adjustments and vouchers.
    remove(
        ~frame["StockCode"].str.fullmatch(r"\d{5}[A-Z]{0,2}"), "non_merchandise_lines"
    )
    remove(frame.duplicated(), "exact_duplicate_lines")
    frame = frame.rename(
        columns={
            "CustomerID": "user_id",
            "StockCode": "product_id",
            "InvoiceNo": "invoice_id",
            "InvoiceDate": "timestamp",
            "Description": "product_name",
            "Quantity": "quantity",
            "UnitPrice": "unit_price",
        }
    )
    before = len(frame)
    # One invoice/product is one purchase event, even if the invoice repeats a line.
    events = frame.groupby(
        ["user_id", "product_id", "invoice_id"], sort=True, as_index=False
    ).agg(
        timestamp=("timestamp", "min"),
        product_name=("product_name", "last"),
        quantity=("quantity", "sum"),
        unit_price=("unit_price", "last"),
    )
    events = events.sort_values(
        ["timestamp", "user_id", "invoice_id", "product_id"], kind="stable"
    ).reset_index(drop=True)
    events["interaction_type"] = "purchase"
    events["interaction_score"] = 1.0
    counts.update(
        {
            "merged_invoice_product_lines": before - len(events),
            "purchase_events": len(events),
            "users": events.user_id.nunique(),
            "products": events.product_id.nunique(),
        }
    )
    if events.empty:
        raise ValueError("No valid purchases remain after cleaning")
    return events, {key: int(value) for key, value in counts.items()}


def catalog_from_events(events: pd.DataFrame) -> pd.DataFrame:
    """Derive metadata only from this snapshot, never from a future evaluation fold."""
    catalog = (
        events.sort_values(["timestamp", "invoice_id"], kind="stable")
        .drop_duplicates("product_id", keep="last")[["product_id", "product_name"]]
        .copy()
    )
    catalog["category"] = None  # UCI does not provide a product taxonomy.
    return catalog.sort_values("product_id").reset_index(drop=True)


def prepare_dataset(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame, dict]:
    """Read the real workbook and persist cleaned events plus provenance."""
    workbook = download_source(data_dir)
    raw = pd.read_excel(workbook, engine="openpyxl")
    events, quality = clean_retail(raw)
    snapshot_bytes = events.to_csv(
        index=False, date_format="%Y-%m-%dT%H:%M:%S"
    ).encode()
    fingerprint = hashlib.sha256(PIPELINE_VERSION.encode() + snapshot_bytes).hexdigest()
    processed = data_dir / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "purchases.csv").write_bytes(snapshot_bytes)
    metadata = {
        "name": "UCI Online Retail",
        "source_url": SOURCE_PAGE,
        "download_url": SOURCE_URL,
        "license": "CC BY 4.0",
        "citation": "Chen, D. (2015). Online Retail. DOI: 10.24432/C5BW33",
        "pipeline_version": PIPELINE_VERSION,
        "raw_sha256": sha256_file(workbook),
        "dataset_sha256": fingerprint,
        "processed_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "date_start": events.timestamp.min().isoformat(),
        "date_end": events.timestamp.max().isoformat(),
        "quality": quality,
    }
    return events, metadata


def load_prepared(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load existing processed purchases; API requests never download or generate data."""
    path = data_dir / "processed" / "purchases.csv"
    if not path.exists():
        raise RuntimeError(
            "Missing prepared data. Run python -m src.train_model first."
        )
    return pd.read_csv(
        path,
        dtype={"user_id": "str", "product_id": "str", "invoice_id": "str"},
        parse_dates=["timestamp"],
    )
