"""Behavior tests protect recommendation meaning, not just response shape."""

import pytest
from src.data_loader import catalog_from_events
from src.recommender import EcommerceRecommender


def test_cosine_and_weighted_scores_have_real_evidence(model):
    neighbors = model.neighbors("U1")
    assert [row["user_id"] for row in neighbors] == ["U2", "U3"]
    assert neighbors[0]["similarity"] == pytest.approx(0.5)
    recs, strategy = model.recommend("U1", 2)
    assert strategy == "user_cosine"
    assert [rec.product_id for rec in recs] == ["P3", "P4"]
    assert recs[0].score == pytest.approx(0.353553, abs=1e-6)
    assert recs[0].evidence[0]["user_id"] == "U2"
    assert recs[0].evidence[0]["contribution"] == recs[0].score


def test_seen_exclusion_fallback_and_catalog_exhaustion(model):
    recs, _ = model.recommend("U1", 50)
    assert [rec.product_id for rec in recs] == ["P3", "P4", "P5"]
    assert recs[-1].source == "popularity"
    assert len({rec.product_id for rec in recs}) == len(recs)
    assert not {"P1", "P2"} & {rec.product_id for rec in recs}


def test_unknown_and_isolated_users_get_deterministic_popularity(model):
    recs, strategy = model.recommend("NEW_CUSTOMER", 3)
    assert strategy == "popularity"
    assert [rec.product_id for rec in recs] == ["P1", "P2", "P3"]
    assert all(rec.evidence == [] for rec in recs)
    recs, strategy = model.recommend("U4", 2)
    assert strategy == "popularity"
    assert all(rec.product_id != "P5" for rec in recs)


def test_self_excluded_even_with_identical_vectors(purchases):
    twin = purchases.loc[purchases.user_id == "U1"].assign(user_id="TWIN")
    import pandas as pd

    events = pd.concat([purchases, twin])
    model = EcommerceRecommender(events, catalog_from_events(events), 2)
    assert model.neighbors("U1")[0]["user_id"] == "TWIN"
    assert "U1" not in {row["user_id"] for row in model.neighbors("U1")}


@pytest.mark.parametrize("k", [0, -1, 51])
def test_invalid_top_k_rejected(model, k):
    with pytest.raises(ValueError):
        model.recommend("U1", k)
