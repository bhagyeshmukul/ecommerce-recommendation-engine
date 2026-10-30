"""Persistent purchase histories, snapshot identity, and recommendation audit logs."""

from __future__ import annotations
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(64), unique=True, nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    category = Column(String(120), nullable=True, index=True)
    popularity_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserInteraction(Base):
    __tablename__ = "user_interactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        String(64), ForeignKey("users.user_id"), nullable=False, index=True
    )
    product_id = Column(
        String(64), ForeignKey("products.product_id"), nullable=False, index=True
    )
    interaction_type = Column(String(50), nullable=False)
    interaction_score = Column(Float, nullable=False)
    invoice_id = Column(String(64), nullable=True)
    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)


class DatasetSnapshot(Base):
    """A singleton certifies that the seed and serving bundle use the same data."""

    __tablename__ = "dataset_snapshot"
    id = Column(Integer, primary_key=True)
    dataset_sha256 = Column(String(64), nullable=False)
    users = Column(Integer, nullable=False)
    products = Column(Integer, nullable=False)
    interactions = Column(Integer, nullable=False)


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    top_k = Column(Integer, nullable=False)
    recommended_products = Column(JSON, nullable=False)
    recommendation_strategy = Column(String(120), nullable=False)
    model_version = Column(String(32), nullable=False, default="legacy")
    request_payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
