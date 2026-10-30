"""Verified bundle loading and the thin boundary between model and persistence."""

from __future__ import annotations
import importlib.metadata
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DatasetSnapshot, Product, RecommendationLog, UserInteraction
from src.data_loader import sha256_file
from src.recommender import EcommerceRecommender
from src.train_model import BUNDLE_DIR
from src.utils import load_model


@dataclass
class ModelBundle:
    model: EcommerceRecommender
    manifest: dict
    metrics: dict


def load_bundle(directory: Path = BUNDLE_DIR) -> ModelBundle:
    """Reject incomplete, corrupted or incompatible bundles before accepting traffic."""
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(
            "Model missing. Run python -m src.train_model, then python -m src.seed_database."
        )
    manifest = json.loads(manifest_path.read_text())
    for filename in ["recommender.joblib", "evaluation.json"]:
        path = directory / filename
        if not path.exists() or sha256_file(path) != manifest["files"][filename]:
            raise RuntimeError(
                f"Bundle checksum mismatch: {filename}. Retrain before serving."
            )
    for package, expected in manifest["identity"]["versions"].items():
        if importlib.metadata.version(package) != expected:
            raise RuntimeError(
                f"{package} differs from the training environment. Install requirements.txt and retrain."
            )
    model = load_model(directory / "recommender.joblib")
    metrics = json.loads((directory / "evaluation.json").read_text())
    if (
        model.model_version != manifest["model_version"]
        or metrics["model_version"] != model.model_version
        or metrics["dataset_sha256"] != manifest["dataset"]["dataset_sha256"]
    ):
        raise RuntimeError("Model, manifest and evaluation identities disagree")
    return ModelBundle(model, manifest, metrics)


def verify_snapshot(db: Session, bundle: ModelBundle) -> None:
    snapshot = db.get(DatasetSnapshot, 1)
    quality = bundle.manifest["dataset"]["quality"]
    if (
        snapshot is None
        or snapshot.dataset_sha256 != bundle.manifest["dataset"]["dataset_sha256"]
        or (snapshot.users, snapshot.products, snapshot.interactions)
        != (quality["users"], quality["products"], quality["purchase_events"])
    ):
        raise RuntimeError(
            "Database snapshot differs from model. Seed the matching data into a fresh demo database."
        )


def get_recommendations(
    bundle: ModelBundle, user_id: str, top_k: int, strategy: str, db: Session
) -> dict:
    recs, actual_strategy = bundle.model.recommend(user_id, top_k, strategy)
    payload = [rec.to_dict() for rec in recs]
    # Persist what was actually served, including evidence and model identity.
    log = RecommendationLog(
        user_id=user_id,
        top_k=top_k,
        recommended_products=payload,
        recommendation_strategy=actual_strategy,
        model_version=bundle.model.model_version,
        request_payload={"user_id": user_id, "top_k": top_k, "strategy": strategy},
    )
    db.add(log)
    db.commit()
    return {
        "user_id": user_id,
        "recommended_products": payload,
        "recommendation_strategy": actual_strategy,
        "model_version": bundle.model.model_version,
        "request_id": log.id,
    }


def get_user_history(db: Session, user_id: str, limit: int) -> list[dict]:
    query = (
        select(UserInteraction, Product)
        .join(Product, Product.product_id == UserInteraction.product_id)
        .where(UserInteraction.user_id == user_id)
        .order_by(UserInteraction.timestamp.desc(), UserInteraction.id.desc())
        .limit(limit)
    )
    return [
        {
            "product_id": event.product_id,
            "product_name": product.product_name,
            "category": product.category,
            "interaction_type": event.interaction_type,
            "interaction_score": event.interaction_score,
            "invoice_id": event.invoice_id,
            "quantity": event.quantity,
            "unit_price": event.unit_price,
            "timestamp": event.timestamp.isoformat(),
        }
        for event, product in db.execute(query)
    ]


def get_latest_logs(db: Session, limit: int) -> list[RecommendationLog]:
    return list(
        db.scalars(
            select(RecommendationLog)
            .order_by(RecommendationLog.created_at.desc(), RecommendationLog.id.desc())
            .limit(limit)
        )
    )
