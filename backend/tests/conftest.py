"""Deterministic tiny purchases keep unit tests fast, offline and artifact-independent."""

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import DatasetSnapshot, Product, User, UserInteraction
from app.services.recommendation_service import ModelBundle
from src.data_loader import catalog_from_events
from src.recommender import EcommerceRecommender


@pytest.fixture
def purchases():
    rows = [
        ("U1", "P1"),
        ("U1", "P2"),
        ("U2", "P1"),
        ("U2", "P3"),
        ("U3", "P2"),
        ("U3", "P4"),
        ("U4", "P5"),
    ]
    return pd.DataFrame(
        [
            {
                "user_id": user,
                "product_id": product,
                "product_name": f"Product {product}",
                "invoice_id": f"I{i}",
                "timestamp": pd.Timestamp("2011-09-01") + pd.Timedelta(days=i),
                "interaction_type": "purchase",
                "interaction_score": 1.0,
                "quantity": 1.0,
                "unit_price": 2.0,
            }
            for i, (user, product) in enumerate(rows)
        ]
    )


@pytest.fixture
def model(purchases):
    return EcommerceRecommender(
        purchases, catalog_from_events(purchases), n_neighbors=2
    )


@pytest.fixture
def bundle(model, purchases):
    model.model_version = "test-model"
    quality = {
        "users": 4,
        "products": 5,
        "purchase_events": len(purchases),
        "raw_rows": len(purchases),
    }
    manifest = {
        "model_version": "test-model",
        "dataset": {"dataset_sha256": "test-data", "quality": quality},
        "serving": {"neighbors": 2},
    }
    metrics = {
        "k": 10,
        "cohort": {"evaluated_users": 1},
        "collaborative": dict.fromkeys(
            ["precision_at_k", "recall_at_k", "map_at_k", "ndcg_at_k", "coverage"], 0.1
        ),
        "popularity": dict.fromkeys(
            ["precision_at_k", "recall_at_k", "map_at_k", "ndcg_at_k", "coverage"], 0.05
        ),
        "evaluation_type": "offline_novel_purchase_discovery",
        "model_version": "test-model",
        "dataset_sha256": "test-data",
    }
    return ModelBundle(model, manifest, metrics)


@pytest.fixture
def session_factory(bundle, purchases):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([User(user_id=user) for user in bundle.model.get_users()])
        db.add_all(
            [
                Product(product_id=row.product_id, product_name=row.product_name)
                for row in catalog_from_events(purchases).itertuples(index=False)
            ]
        )
        for row in purchases.itertuples(index=False):
            db.add(
                UserInteraction(
                    user_id=row.user_id,
                    product_id=row.product_id,
                    invoice_id=row.invoice_id,
                    quantity=row.quantity,
                    unit_price=row.unit_price,
                    interaction_type="purchase",
                    interaction_score=1.0,
                    timestamp=row.timestamp.to_pydatetime(),
                )
            )
        db.add(
            DatasetSnapshot(
                id=1,
                dataset_sha256="test-data",
                users=4,
                products=5,
                interactions=len(purchases),
            )
        )
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def client(monkeypatch, bundle, session_factory):
    from fastapi.testclient import TestClient
    import app.main as main
    from app.db.session import get_db

    monkeypatch.setattr(main, "load_bundle", lambda directory: bundle)
    monkeypatch.setattr(main, "SessionLocal", session_factory)

    def dependency():
        with session_factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    main.app.dependency_overrides[get_db] = dependency
    with TestClient(main.app) as instance:
        yield instance
    main.app.dependency_overrides.clear()
