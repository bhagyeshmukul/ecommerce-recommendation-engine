from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RecommendedProduct(BaseModel):
    product_id: str
    product_name: str
    category: str
    score: float
    reason: str


class RecommendationResponse(BaseModel):
    user_id: str
    recommended_products: list[RecommendedProduct]
    recommendation_strategy: str


class UserListResponse(BaseModel):
    users: list[str]


class PopularProductsResponse(BaseModel):
    products: list[RecommendedProduct]


class HistoryItem(BaseModel):
    product_id: str
    product_name: str | None = None
    category: str | None = None
    interaction_type: str
    interaction_score: float
    timestamp: str


class MetricsResponse(BaseModel):
    precision_at_k: float
    recall_at_k: float
    map_at_k: float
    coverage: float


class RecommendationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    top_k: int
    recommended_products: list[dict[str, Any]]
    recommendation_strategy: str
    request_payload: dict[str, Any]
    created_at: datetime
