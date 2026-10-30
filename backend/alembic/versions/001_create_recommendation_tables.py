"""Original PostgreSQL schema; the v2 purchase changes are a separate migration."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "001_create_recommendation_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_user_id", "users", ["user_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("popularity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id"),
    )
    op.create_index("ix_products_id", "products", ["id"])
    op.create_index("ix_products_product_id", "products", ["product_id"])
    op.create_index("ix_products_category", "products", ["category"])

    op.create_table(
        "user_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("product_id", sa.String(length=64), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("interaction_type", sa.String(length=50), nullable=False),
        sa.Column("interaction_score", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_interactions_id", "user_interactions", ["id"])
    op.create_index("ix_user_interactions_user_id", "user_interactions", ["user_id"])
    op.create_index("ix_user_interactions_product_id", "user_interactions", ["product_id"])
    op.create_index("ix_user_interactions_timestamp", "user_interactions", ["timestamp"])

    op.create_table(
        "recommendation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("recommended_products", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommendation_strategy", sa.String(length=120), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendation_logs_id", "recommendation_logs", ["id"])
    op.create_index("ix_recommendation_logs_user_id", "recommendation_logs", ["user_id"])
    op.create_index("ix_recommendation_logs_created_at", "recommendation_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("recommendation_logs")
    op.drop_table("user_interactions")
    op.drop_table("products")
    op.drop_table("users")
