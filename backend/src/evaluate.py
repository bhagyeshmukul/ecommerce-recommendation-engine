from __future__ import annotations

import numpy as np
import pandas as pd

from src.recommender import EcommerceRecommender


def precision_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(recommended[:k]) & relevant) / k


def recall_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(recommended[:k]) & relevant) / len(relevant)


def average_precision_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    hits = 0
    score = 0.0
    for idx, product_id in enumerate(recommended[:k], start=1):
        if product_id in relevant:
            hits += 1
            score += hits / idx
    return score / min(len(relevant), k) if relevant else 0.0


def evaluate_recommender(interactions: pd.DataFrame, products: pd.DataFrame, k: int = 5) -> dict[str, float]:
    sorted_events = interactions.sort_values("timestamp")
    test = sorted_events.groupby("user_id").tail(1)
    train = sorted_events.drop(test.index)
    recommender = EcommerceRecommender(train, products)

    precisions: list[float] = []
    recalls: list[float] = []
    aps: list[float] = []
    covered_products: set[str] = set()

    for user_id, group in test.groupby("user_id"):
        recs, _ = recommender.recommend(str(user_id), top_k=k)
        rec_ids = [rec.product_id for rec in recs]
        relevant = set(group["product_id"].astype(str))
        covered_products.update(rec_ids)
        precisions.append(precision_at_k(rec_ids, relevant, k))
        recalls.append(recall_at_k(rec_ids, relevant, k))
        aps.append(average_precision_at_k(rec_ids, relevant, k))

    catalog_size = max(products["product_id"].nunique(), 1)
    return {
        "precision_at_k": round(float(np.mean(precisions)) if precisions else 0.0, 4),
        "recall_at_k": round(float(np.mean(recalls)) if recalls else 0.0, 4),
        "map_at_k": round(float(np.mean(aps)) if aps else 0.0, 4),
        "coverage": round(len(covered_products) / catalog_size, 4),
    }
