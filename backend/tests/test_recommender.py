import pandas as pd

from src.recommender import EcommerceRecommender


def sample_data():
    products = pd.DataFrame(
        [
            {"product_id": "P1", "product_name": "Phone", "category": "Electronics", "popularity_score": 5},
            {"product_id": "P2", "product_name": "Laptop", "category": "Electronics", "popularity_score": 7},
            {"product_id": "P3", "product_name": "Shoes", "category": "Fashion", "popularity_score": 10},
            {"product_id": "P4", "product_name": "Bottle", "category": "Home", "popularity_score": 3},
        ]
    )
    interactions = pd.DataFrame(
        [
            {"user_id": "U1", "product_id": "P1", "interaction_type": "purchase", "interaction_score": 5, "timestamp": "2026-01-01"},
            {"user_id": "U1", "product_id": "P2", "interaction_type": "click", "interaction_score": 2, "timestamp": "2026-01-02"},
            {"user_id": "U2", "product_id": "P1", "interaction_type": "click", "interaction_score": 2, "timestamp": "2026-01-03"},
            {"user_id": "U2", "product_id": "P3", "interaction_type": "purchase", "interaction_score": 5, "timestamp": "2026-01-04"},
            {"user_id": "U3", "product_id": "P2", "interaction_type": "purchase", "interaction_score": 5, "timestamp": "2026-01-05"},
            {"user_id": "U3", "product_id": "P4", "interaction_type": "click", "interaction_score": 2, "timestamp": "2026-01-06"},
        ]
    )
    return products, interactions


def test_cosine_similarity_calculation():
    products, interactions = sample_data()
    recommender = EcommerceRecommender(interactions, products)

    assert recommender.user_similarity.loc["U1", "U1"] == 1
    assert recommender.user_similarity.loc["U1", "U2"] > 0


def test_recommendation_output_excludes_seen_products():
    products, interactions = sample_data()
    recommender = EcommerceRecommender(interactions, products)

    recommendations, strategy = recommender.recommend("U1", top_k=2)

    assert strategy == "hybrid_collaborative_filtering"
    assert len(recommendations) == 2
    assert all(rec.product_id not in {"P1", "P2"} for rec in recommendations)
    assert all(rec.reason for rec in recommendations)


def test_cold_start_fallback():
    products, interactions = sample_data()
    recommender = EcommerceRecommender(interactions, products)

    recommendations, strategy = recommender.recommend("NEW_USER", top_k=2)

    assert strategy == "popularity"
    assert len(recommendations) == 2
    assert recommendations[0].reason == "Popular product fallback"
