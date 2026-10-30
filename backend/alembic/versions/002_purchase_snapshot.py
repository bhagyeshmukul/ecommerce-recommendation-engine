"""Add real purchase metadata and a snapshot identity without rewriting history."""

from alembic import op
import sqlalchemy as sa

revision = "002_purchase_snapshot"
down_revision = "001_create_recommendation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("products", "category", existing_type=sa.String(120), nullable=True)
    op.add_column(
        "user_interactions", sa.Column("invoice_id", sa.String(64), nullable=True)
    )
    op.add_column("user_interactions", sa.Column("quantity", sa.Float(), nullable=True))
    op.add_column(
        "user_interactions", sa.Column("unit_price", sa.Float(), nullable=True)
    )
    op.add_column(
        "recommendation_logs",
        sa.Column(
            "model_version", sa.String(32), nullable=False, server_default="legacy"
        ),
    )
    op.create_table(
        "dataset_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_sha256", sa.String(64), nullable=False),
        sa.Column("users", sa.Integer(), nullable=False),
        sa.Column("products", sa.Integer(), nullable=False),
        sa.Column("interactions", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("dataset_snapshot")
    op.drop_column("recommendation_logs", "model_version")
    for column in ["unit_price", "quantity", "invoice_id"]:
        op.drop_column("user_interactions", column)
    # Preserve existing purchases when restoring the old non-null category schema.
    op.execute("UPDATE products SET category = 'Uncategorized' WHERE category IS NULL")
    op.alter_column(
        "products", "category", existing_type=sa.String(120), nullable=False
    )
