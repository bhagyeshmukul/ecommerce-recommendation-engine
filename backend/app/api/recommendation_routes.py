from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.recommendation_schema import (
    HistoryItem,
    MetricsResponse,
    PopularProductsResponse,
    RecommendationLogResponse,
    RecommendationResponse,
    UserListResponse,
)
from app.services import recommendation_service


router = APIRouter()


@router.get("/recommend/{user_id}", response_model=RecommendationResponse)
def recommend(user_id: str, top_k: int = Query(default=5, ge=1, le=50), db: Session = Depends(get_db)):
    recommendations, strategy = recommendation_service.get_recommendations(user_id, top_k, db)
    return {
        "user_id": user_id,
        "recommended_products": recommendations,
        "recommendation_strategy": strategy,
    }


@router.get("/users", response_model=UserListResponse)
def users():
    return {"users": recommendation_service.get_user_ids()}


@router.get("/users/{user_id}/history", response_model=list[HistoryItem])
def user_history(user_id: str):
    return recommendation_service.get_user_history(user_id)


@router.get("/products/popular", response_model=PopularProductsResponse)
def popular_products(top_k: int = Query(default=10, ge=1, le=50)):
    return {"products": recommendation_service.get_popular_products(top_k)}


@router.get("/metrics", response_model=MetricsResponse)
def metrics():
    return recommendation_service.get_metrics()


@router.get("/recommendation-logs", response_model=list[RecommendationLogResponse])
def recommendation_logs(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    return recommendation_service.get_latest_logs(db, limit)
