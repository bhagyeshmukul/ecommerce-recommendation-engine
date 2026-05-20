from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import RecommendationLog
from app.services.recommendation_service import get_latest_logs


def test_database_logging_logic():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    db.add(
        RecommendationLog(
            user_id="U1",
            top_k=1,
            recommended_products=[{"product_id": "P1"}],
            recommendation_strategy="test",
            request_payload={"user_id": "U1"},
        )
    )
    db.commit()

    logs = get_latest_logs(db, limit=5)

    assert len(logs) == 1
    assert logs[0].user_id == "U1"
    assert logs[0].recommended_products[0]["product_id"] == "P1"
