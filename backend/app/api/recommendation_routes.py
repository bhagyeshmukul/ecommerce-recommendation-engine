"""HTTP validation and routing; ML scoring stays in src/recommender.py."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.recommendation_schema import (
    HistoryItem,
    MetricsResponse,
    RecommendationLogResponse,
    RecommendationResponse,
)
from app.services import recommendation_service as service

router = APIRouter()
UserId = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


def get_bundle(request: Request) -> service.ModelBundle:
    return request.app.state.bundle


Bundle = Annotated[service.ModelBundle, Depends(get_bundle)]
Database = Annotated[Session, Depends(get_db)]


@router.get("/recommend/{user_id}", response_model=RecommendationResponse)
def recommend(
    user_id: UserId,
    bundle: Bundle,
    db: Database,
    top_k: int = Query(5, ge=1, le=50),
    strategy: Literal["collaborative", "popularity"] = "collaborative",
):
    return service.get_recommendations(bundle, user_id, top_k, strategy, db)


@router.get("/users")
def users(
    bundle: Bundle,
    q: str = Query("", max_length=64),
    limit: int = Query(50, ge=1, le=5000),
):
    all_users = bundle.model.get_users()
    matching = [user for user in all_users if q.lower() in user.lower()]
    return {
        "users": matching[:limit],
        "total": len(all_users),
        "matching": len(matching),
    }


@router.get("/users/{user_id}/history", response_model=list[HistoryItem])
def history(user_id: UserId, db: Database, limit: int = Query(20, ge=1, le=100)):
    return service.get_user_history(db, user_id, limit)


@router.get("/users/{user_id}/neighbors")
def neighbors(user_id: UserId, bundle: Bundle, limit: int = Query(5, ge=1, le=10)):
    return {"user_id": user_id, "neighbors": bundle.model.neighbors(user_id, limit)}


@router.get("/products/popular")
def popular(bundle: Bundle, top_k: int = Query(5, ge=1, le=50)):
    return {
        "products": [
            rec.to_dict() for rec in bundle.model.popular_recommendations(top_k)
        ]
    }


@router.get("/metrics", response_model=MetricsResponse)
def metrics(bundle: Bundle):
    return bundle.metrics


@router.get("/model")
def model_metadata(bundle: Bundle):
    return bundle.manifest


@router.get("/recommendation-logs", response_model=list[RecommendationLogResponse])
def logs(db: Database, limit: int = Query(10, ge=1, le=100)):
    return service.get_latest_logs(db, limit)
