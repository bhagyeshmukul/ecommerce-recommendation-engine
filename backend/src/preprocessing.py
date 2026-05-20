from __future__ import annotations

import pandas as pd


REQUIRED_INTERACTION_COLUMNS = {
    "user_id",
    "product_id",
    "interaction_type",
    "interaction_score",
    "timestamp",
}


def clean_interactions(interactions: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_INTERACTION_COLUMNS.difference(interactions.columns)
    if missing:
        raise ValueError(f"Missing interaction columns: {sorted(missing)}")

    cleaned = interactions.copy()
    cleaned = cleaned.dropna(subset=["user_id", "product_id", "interaction_score"])
    cleaned["user_id"] = cleaned["user_id"].astype(str)
    cleaned["product_id"] = cleaned["product_id"].astype(str)
    cleaned["interaction_score"] = pd.to_numeric(cleaned["interaction_score"], errors="coerce").fillna(0.0)
    cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"], errors="coerce")
    cleaned = cleaned.dropna(subset=["timestamp"])
    return cleaned


def create_user_item_matrix(interactions: pd.DataFrame) -> pd.DataFrame:
    cleaned = clean_interactions(interactions)
    matrix = cleaned.pivot_table(
        index="user_id",
        columns="product_id",
        values="interaction_score",
        aggfunc="sum",
        fill_value=0.0,
    )
    return matrix.sort_index(axis=0).sort_index(axis=1)
