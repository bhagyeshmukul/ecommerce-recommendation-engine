from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Product, User, UserInteraction
from app.db.session import SessionLocal
from src.data_loader import load_or_generate_dataset


def seed_database() -> None:
    users, products, interactions = load_or_generate_dataset()
    db = SessionLocal()
    try:
        if db.query(User).first():
            return

        db.bulk_save_objects([User(user_id=str(row.user_id)) for row in users.itertuples(index=False)])
        db.bulk_save_objects(
            [
                Product(
                    product_id=str(row.product_id),
                    product_name=str(row.product_name),
                    category=str(row.category),
                    popularity_score=float(row.popularity_score),
                )
                for row in products.itertuples(index=False)
            ]
        )
        db.bulk_save_objects(
            [
                UserInteraction(
                    user_id=str(row.user_id),
                    product_id=str(row.product_id),
                    interaction_type=str(row.interaction_type),
                    interaction_score=float(row.interaction_score),
                    timestamp=row.timestamp.to_pydatetime() if hasattr(row.timestamp, "to_pydatetime") else row.timestamp,
                )
                for row in interactions.itertuples(index=False)
            ]
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
