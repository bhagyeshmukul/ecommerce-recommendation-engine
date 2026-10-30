"""Seed one verified purchase snapshot in a transaction; never overwrite user data."""

from __future__ import annotations
from pathlib import Path
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.db.models import DatasetSnapshot, Product, User, UserInteraction
from app.db.session import SessionLocal
from app.services.recommendation_service import (
    ModelBundle,
    load_bundle,
    verify_snapshot,
)
from src.data_loader import DATA_DIR, catalog_from_events, load_prepared, sha256_file


def seed_database(
    db: Session | None = None,
    bundle: ModelBundle | None = None,
    data_dir: Path = DATA_DIR,
) -> None:
    """Allow injected sessions for tests; the CLI owns and closes its session."""
    if db is None:
        with SessionLocal() as session:
            seed_database(session, bundle, data_dir)
        return
    bundle = bundle or load_bundle()
    if db.get(DatasetSnapshot, 1) is not None:
        verify_snapshot(db, bundle)
        expected = bundle.manifest["dataset"]["quality"]
        actual = [
            db.scalar(select(func.count()).select_from(table))
            for table in [User, Product, UserInteraction]
        ]
        if actual != [
            expected["users"],
            expected["products"],
            expected["purchase_events"],
        ]:
            raise RuntimeError(
                "Existing snapshot is incomplete. Use a fresh demo database."
            )
        print("Matching dataset already seeded; no rows changed.", flush=True)
        return
    if any(
        db.scalar(select(func.count()).select_from(table))
        for table in [User, Product, UserInteraction]
    ):
        raise RuntimeError(
            "Database contains other data. Use a fresh dedicated demo database; existing rows were preserved."
        )
    path = data_dir / "processed" / "purchases.csv"
    if (
        not path.exists()
        or sha256_file(path) != bundle.manifest["dataset"]["processed_sha256"]
    ):
        raise RuntimeError(
            "Prepared data does not match model manifest. Retrain before seeding."
        )
    events = load_prepared(data_dir)
    products = catalog_from_events(events)
    popularity = events.groupby("product_id").user_id.nunique()
    try:
        db.execute(
            insert(User), [{"user_id": user} for user in bundle.model.get_users()]
        )
        db.execute(
            insert(Product),
            [
                {
                    "product_id": row.product_id,
                    "product_name": row.product_name,
                    "category": None,
                    "popularity_score": float(popularity[row.product_id]),
                }
                for row in products.itertuples(index=False)
            ],
        )
        # Small batches bound SQL statement size and client memory.
        fields = [
            "user_id",
            "product_id",
            "invoice_id",
            "timestamp",
            "quantity",
            "unit_price",
            "interaction_type",
            "interaction_score",
        ]
        for start in range(0, len(events), 5000):
            rows = events.iloc[start : start + 5000][fields].copy()
            rows["timestamp"] = rows.timestamp.map(lambda value: value.to_pydatetime())
            db.execute(insert(UserInteraction), rows.to_dict(orient="records"))
        quality = bundle.manifest["dataset"]["quality"]
        db.add(
            DatasetSnapshot(
                id=1,
                dataset_sha256=bundle.manifest["dataset"]["dataset_sha256"],
                users=quality["users"],
                products=quality["products"],
                interactions=quality["purchase_events"],
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    print(f"Seeded {len(events):,} real purchase events.", flush=True)


if __name__ == "__main__":
    seed_database()
