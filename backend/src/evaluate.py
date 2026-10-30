"""Chronological validation/test evaluation against a fair popularity baseline.

The task is novel-product discovery: already-purchased products are excluded both
from recommendations and the target set. We rank the full available catalog,
not a sampled set of easy negatives. This measures offline ranking, not CTR.
"""

from __future__ import annotations
import math

import numpy as np
import pandas as pd

from src.data_loader import catalog_from_events
from src.recommender import EcommerceRecommender

VALIDATION_START = pd.Timestamp("2011-11-01")
TEST_START = pd.Timestamp("2011-12-01")
K = 10


def ranking_metrics(
    recommended: list[str], relevant: set[str], k: int
) -> dict[str, float]:
    """Precision uses k even when the available catalog returns a shorter list."""
    if k < 1:
        raise ValueError("k must be positive")
    hits, precision_sum, dcg = 0, 0.0, 0.0
    found = set()
    for rank, product in enumerate(recommended[:k], 1):
        if product in relevant and product not in found:
            hits += 1
            precision_sum += hits / rank
            dcg += 1 / math.log2(rank + 1)
            found.add(product)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return {
        "precision_at_k": hits / k,
        "recall_at_k": hits / len(relevant) if relevant else 0.0,
        "map_at_k": precision_sum / min(len(relevant), k) if relevant else 0.0,
        "ndcg_at_k": dcg / ideal if ideal else 0.0,
    }


def chronological_split(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Use global boundaries: no other customer's future purchases enter training."""
    return (
        events.loc[events.timestamp < VALIDATION_START].copy(),
        events.loc[
            (events.timestamp >= VALIDATION_START) & (events.timestamp < TEST_START)
        ].copy(),
        events.loc[events.timestamp >= TEST_START].copy(),
    )


def evaluate_fold(
    model: EcommerceRecommender, targets: pd.DataFrame, k: int = K
) -> dict:
    """Evaluate both methods on exactly the same warm-user discovery targets."""
    catalog = set(model.matrix.products)
    results = {"collaborative": [], "popularity": []}
    covered = {key: set() for key in results}
    counts = {
        "target_users": int(targets.user_id.nunique()),
        "evaluated_users": 0,
        "cold_start_users": 0,
        "users_without_eligible_targets": 0,
        "target_user_product_pairs": 0,
        "cold_start_target_pairs": 0,
        "previously_seen_target_pairs": 0,
        "out_of_catalog_target_pairs": 0,
        "eligible_target_pairs": 0,
        "fallback_users": 0,
    }
    for user, group in targets.groupby("user_id", sort=True):
        purchased = set(group.product_id)
        counts["target_user_product_pairs"] += len(purchased)
        if user not in model.user_lookup:
            counts["cold_start_users"] += 1
            counts["cold_start_target_pairs"] += len(purchased)
            continue
        seen = {model.matrix.products[i] for i in model.seen_indices(user)}
        counts["previously_seen_target_pairs"] += len(purchased & seen)
        counts["out_of_catalog_target_pairs"] += len(purchased - seen - catalog)
        relevant = (purchased & catalog) - seen
        if not relevant:
            counts["users_without_eligible_targets"] += 1
            continue
        counts["evaluated_users"] += 1
        counts["eligible_target_pairs"] += len(relevant)
        for method in results:
            recs, strategy = model.recommend(user, k, strategy=method)
            ids = [rec.product_id for rec in recs]
            if method == "collaborative" and strategy == "popularity":
                counts["fallback_users"] += 1
            results[method].append(ranking_metrics(ids, relevant, k))
            covered[method].update(ids)
    scores = {}
    for method, rows in results.items():
        scores[method] = {
            key: float(np.mean([row[key] for row in rows])) if rows else None
            for key in ["precision_at_k", "recall_at_k", "map_at_k", "ndcg_at_k"]
        }
        scores[method]["coverage"] = (
            len(covered[method]) / len(catalog) if catalog else 0.0
        )
    baseline, candidate = (
        scores["popularity"]["ndcg_at_k"],
        scores["collaborative"]["ndcg_at_k"],
    )
    return {
        "k": k,
        "cohort": counts,
        **scores,
        "ndcg_relative_change_percent": (
            (candidate / baseline - 1) * 100
            if baseline and candidate is not None
            else None
        ),
    }


def evaluate_recommender(events: pd.DataFrame) -> tuple[dict, int]:
    """Choose on November, lock the configuration, then evaluate December once."""
    train, validation, test = chronological_split(events)
    if any(fold.empty for fold in [train, validation, test]):
        raise ValueError(
            "Dataset must cover training, November validation, and December test windows"
        )
    validation_runs = []
    for neighbors in [10, 25, 50]:
        model = EcommerceRecommender(train, catalog_from_events(train), neighbors)
        result = evaluate_fold(model, validation)
        if not result["cohort"]["evaluated_users"]:
            raise ValueError("No eligible validation users")
        validation_runs.append(
            {
                "n_neighbors": neighbors,
                "ndcg_at_k": result["collaborative"]["ndcg_at_k"],
            }
        )
        print(
            f"Validation neighbors={neighbors}: NDCG@{K}={result['collaborative']['ndcg_at_k']:.6f}",
            flush=True,
        )
    # Smaller neighborhoods win exact ties; test results never select parameters.
    best = max(
        validation_runs, key=lambda run: (run["ndcg_at_k"], -run["n_neighbors"])
    )["n_neighbors"]
    history = events.loc[events.timestamp < TEST_START]
    test_model = EcommerceRecommender(history, catalog_from_events(history), best)
    report = evaluate_fold(test_model, test)
    if not report["cohort"]["evaluated_users"]:
        raise ValueError("No eligible test users")
    report.update(
        {
            "evaluation_type": "offline_novel_purchase_discovery",
            "engagement_lift": None,
            "train_before": VALIDATION_START.isoformat(),
            "validation_start": VALIDATION_START.isoformat(),
            "validation_end_exclusive": TEST_START.isoformat(),
            "test_start": TEST_START.isoformat(),
            "test_end": test.timestamp.max().isoformat(),
            "test_catalog_size": len(test_model.matrix.products),
            "selected_neighbors": best,
            "validation_runs": validation_runs,
            "protocol": "Global chronological split; warm users; unseen products; full training catalog; macro averages; no sampled negatives.",
        }
    )
    return report, best
