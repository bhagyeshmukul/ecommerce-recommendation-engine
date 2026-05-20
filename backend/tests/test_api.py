from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base
from app.db.session import get_db
from app.main import app


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_recommend_endpoint_logs_request():
    response = client.get("/recommend/U0001?top_k=3")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "U0001"
    assert len(body["recommended_products"]) == 3


def test_users_endpoint():
    response = client.get("/users")

    assert response.status_code == 200
    assert len(response.json()["users"]) > 0


def test_recommendation_logs_endpoint():
    client.get("/recommend/U0002?top_k=2")
    response = client.get("/recommendation-logs")

    assert response.status_code == 200
    assert len(response.json()) >= 1
