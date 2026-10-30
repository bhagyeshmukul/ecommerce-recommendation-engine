"""Public API contracts. Scores identify their source rather than implying probability."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class NeighborEvidence(BaseModel):
    user_id: str
    similarity: float
    contribution: float


class RecommendedProduct(BaseModel):
    product_id: str
    product_name: str
    category: str | None
    score: float
    reason: str
    source: str
    supporting_users: int
    evidence: list[NeighborEvidence]


class RecommendationResponse(BaseModel):
    user_id: str
    recommended_products: list[RecommendedProduct]
    recommendation_strategy: str
    model_version: str
    request_id: int


class HistoryItem(BaseModel):
    product_id: str
    product_name: str
    category: str | None
    interaction_type: str
    interaction_score: float
    invoice_id: str | None
    quantity: float | None
    unit_price: float | None
    timestamp: str


class RecommendationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: str
    top_k: int
    recommended_products: list[dict[str, Any]]
    recommendation_strategy: str
    model_version: str
    request_payload: dict[str, Any]
    created_at: datetime


class RankingScores(BaseModel):
    precision_at_k: float | None
    recall_at_k: float | None
    map_at_k: float | None
    ndcg_at_k: float | None
    coverage: float


class MetricsResponse(BaseModel):
    # Additional protocol fields are intentionally retained in the public report.
    model_config = ConfigDict(extra="allow")
    k: int
    collaborative: RankingScores
    popularity: RankingScores
    cohort: dict[str, int]
    evaluation_type: str
    model_version: str
    dataset_sha256: str
