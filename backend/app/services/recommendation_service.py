from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import models
from app.schemas.recommendation_schema import RecommendedProduct
from src.data_loader import load_or_generate_dataset
from src.evaluate import evaluate_recommender
from src.recommender import EcommerceRecommender
from src.utils import load_model


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "ecommerce_recommender.joblib"


@lru_cache(maxsize=1)
def get_recommender() -> EcommerceRecommender:
    if MODEL_PATH.exists():
        return load_model(MODEL_PATH)
    _, products, interactions = load_or_generate_dataset()
    return EcommerceRecommender(interactions, products)


@lru_cache(maxsize=1)
def get_metrics() -> dict[str, float]:
    _, products, interactions = load_or_generate_dataset()
    return evaluate_recommender(interactions, products, k=5)


def serialize_recommendations(recommendations) -> list[dict[str, object]]:
    return [
        {
            "product_id": rec.product_id,
            "product_name": rec.product_name,
            "category": rec.category,
            "score": rec.score,
            "reason": rec.reason,
        }
        for rec in recommendations
    ]


def get_recommendations(user_id: str, top_k: int, db: Session) -> tuple[list[RecommendedProduct], str]:
    recommender = get_recommender()
    recommendations, strategy = recommender.recommend(user_id=user_id, top_k=top_k)
    payload = serialize_recommendations(recommendations)

    log = models.RecommendationLog(
        user_id=user_id,
        top_k=top_k,
        recommended_products=payload,
        recommendation_strategy=strategy,
        request_payload={"user_id": user_id, "top_k": top_k},
    )
    db.add(log)
    db.commit()

    return [RecommendedProduct(**item) for item in payload], strategy


def get_popular_products(top_k: int = 10) -> list[RecommendedProduct]:
    recommendations = get_recommender()._popular_recommendations(top_k)
    return [RecommendedProduct(**item) for item in serialize_recommendations(recommendations)]


def get_user_ids() -> list[str]:
    return get_recommender().get_users()


def get_user_history(user_id: str) -> list[dict[str, object]]:
    return get_recommender().get_user_history(user_id)


def get_latest_logs(db: Session, limit: int = 20) -> list[models.RecommendationLog]:
    return (
        db.query(models.RecommendationLog)
        .order_by(models.RecommendationLog.created_at.desc(), models.RecommendationLog.id.desc())
        .limit(limit)
        .all()
    )
