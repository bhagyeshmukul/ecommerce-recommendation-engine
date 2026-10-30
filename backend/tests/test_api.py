"""API contracts, observed behavior and dependency failures use an isolated database."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from app.db.models import RecommendationLog


def test_recommendations_log_model_and_evidence(client, session_factory):
    response = client.get("/recommend/U1?top_k=2")
    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "test-model"
    assert body["recommendation_strategy"] == "user_cosine"
    assert [item["product_id"] for item in body["recommended_products"]] == ["P3", "P4"]
    assert body["recommended_products"][0]["evidence"]
    with session_factory() as db:
        log = db.get(RecommendationLog, body["request_id"])
        assert log.recommended_products == body["recommended_products"]
        assert log.model_version == "test-model"


@pytest.mark.parametrize(
    "path",
    [
        "/recommend/U1?top_k=0",
        "/recommend/U1?top_k=51",
        "/recommend/U1?strategy=magic",
        "/users?limit=5001",
        "/users/U1/history?limit=101",
        "/recommend/space%20id",
    ],
)
def test_validation(client, path):
    assert client.get(path).status_code == 422


def test_new_customer_and_baseline(client):
    cold = client.get("/recommend/NEW_CUSTOMER").json()
    assert cold["recommendation_strategy"] == "popularity"
    assert client.get("/users/NEW_CUSTOMER/history").json() == []
    assert client.get("/users/NEW_CUSTOMER/neighbors").json()["neighbors"] == []
    baseline = client.get("/recommend/U1?strategy=popularity").json()
    assert baseline["recommendation_strategy"] == "popularity"
    assert {row["product_id"] for row in baseline["recommended_products"]}.isdisjoint(
        {"P1", "P2"}
    )


def test_metadata_history_metrics_logs_and_readiness(client):
    assert client.get("/users?q=U1").json()["users"] == ["U1"]
    assert len(client.get("/users/U1/history?limit=1").json()) == 1
    assert client.get("/users/U1/neighbors").json()["neighbors"][0][
        "similarity"
    ] == pytest.approx(0.5)
    assert client.get("/model").json()["model_version"] == "test-model"
    assert client.get("/metrics").json()["k"] == 10
    assert client.get("/ready").status_code == 200
    assert client.get("/health").status_code == 200
    client.get("/recommend/U1")
    assert client.get("/recommendation-logs?limit=1").json()[0]["user_id"] == "U1"


def test_database_failure_returns_service_unavailable(client, monkeypatch):
    def broken(*args, **kwargs):
        raise OperationalError("unavailable", {}, None)

    monkeypatch.setattr("app.services.recommendation_service.get_latest_logs", broken)
    response = client.get("/recommendation-logs")
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_readiness_detects_snapshot_mismatch(client, session_factory):
    from app.db.models import DatasetSnapshot

    with session_factory() as db:
        db.get(DatasetSnapshot, 1).dataset_sha256 = "other"
        db.commit()
    assert client.get("/ready").status_code == 503
