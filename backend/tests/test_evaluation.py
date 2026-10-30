"""Prevent inflated metrics from future leakage, inconsistent baselines or repeats."""

import math
import pandas as pd
import pytest
from src.data_loader import catalog_from_events
from src.evaluate import (
    chronological_split,
    evaluate_fold,
    evaluate_recommender,
    ranking_metrics,
)


def test_hand_computed_ranking_metrics():
    values = ranking_metrics(["X", "A", "B"], {"A", "B"}, 3)
    assert values["precision_at_k"] == pytest.approx(2 / 3)
    assert values["recall_at_k"] == 1
    assert values["map_at_k"] == pytest.approx((1 / 2 + 2 / 3) / 2)
    assert values["ndcg_at_k"] == pytest.approx(
        (1 / math.log2(3) + 0.5) / (1 + 1 / math.log2(3))
    )
    assert ranking_metrics(["A", "A"], {"A"}, 2)["recall_at_k"] == 1
    assert ranking_metrics([], set(), 3)["ndcg_at_k"] == 0


def test_global_split_and_prefix_catalog(purchases):
    events = purchases.copy()
    events.loc[0, "timestamp"] = pd.Timestamp("2011-11-01")
    events.loc[1, "timestamp"] = pd.Timestamp("2011-12-01")
    train, validation, test = chronological_split(events)
    assert train.timestamp.max() < validation.timestamp.min() < test.timestamp.min()
    future = events.iloc[[0]].assign(product_id="FUTURE", product_name="Future product")
    assert "FUTURE" not in set(catalog_from_events(train).product_id)
    assert "FUTURE" in set(catalog_from_events(future).product_id)


def test_same_cohort_excludes_repeats_and_reports_unavailable_targets(model, purchases):
    targets = pd.DataFrame(
        [
            {"user_id": "U1", "product_id": product}
            for product in ["P1", "P3", "NEW_PRODUCT"]
        ]
        + [
            {"user_id": "COLD", "product_id": "P2"},
            {"user_id": "U2", "product_id": "P1"},
        ]
    )
    result = evaluate_fold(model, targets, 2)
    assert result["cohort"]["evaluated_users"] == 1
    assert result["cohort"]["cold_start_users"] == 1
    assert result["cohort"]["previously_seen_target_pairs"] == 2
    assert result["cohort"]["out_of_catalog_target_pairs"] == 1
    assert result["collaborative"]["recall_at_k"] == 1
    assert result["popularity"]["recall_at_k"] == 1


def test_configuration_is_selected_only_on_validation(monkeypatch, purchases):
    # Changing the test score must not change selected neighbors.
    events = pd.concat(
        [
            purchases,
            purchases.assign(timestamp=pd.Timestamp("2011-11-05")),
            purchases.assign(timestamp=pd.Timestamp("2011-12-05")),
        ]
    )
    seen = []

    def fake_fold(model, targets, k=10):
        month = targets.timestamp.min().month
        seen.append((month, model.n_neighbors, set(model.matrix.products)))
        value = {10: 0.1, 25: 0.3, 50: 0.2}[model.n_neighbors] if month == 11 else 0.0
        return {
            "cohort": {"evaluated_users": 1},
            "collaborative": {"ndcg_at_k": value},
            "popularity": {"ndcg_at_k": 0.1},
        }

    monkeypatch.setattr("src.evaluate.evaluate_fold", fake_fold)
    report, selected = evaluate_recommender(events)
    assert selected == 25
    assert [month for month, _, _ in seen] == [11, 11, 11, 12]
    assert seen[-1][1] == 25
