from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from src.preprocessing import create_user_item_matrix


@dataclass(frozen=True)
class Recommendation:
    product_id: str
    product_name: str
    category: str
    score: float
    reason: str


class EcommerceRecommender:
    def __init__(self, interactions: pd.DataFrame, products: pd.DataFrame):
        self.interactions = interactions.copy()
        self.products = products.copy()
        self.user_item_matrix = create_user_item_matrix(self.interactions)
        self.user_similarity = self._cosine_frame(self.user_item_matrix)
        self.item_similarity = self._cosine_frame(self.user_item_matrix.T)
        self.popular_products = self._build_popular_products()

    @staticmethod
    def _cosine_frame(matrix: pd.DataFrame) -> pd.DataFrame:
        if matrix.empty:
            return pd.DataFrame(index=matrix.index, columns=matrix.index, dtype=float)
        values = cosine_similarity(matrix.values)
        return pd.DataFrame(values, index=matrix.index, columns=matrix.index)

    def _build_popular_products(self) -> pd.DataFrame:
        popularity = (
            self.interactions.groupby("product_id")["interaction_score"]
            .sum()
            .rename("computed_popularity")
            .reset_index()
        )
        products = self.products.merge(popularity, on="product_id", how="left")
        products["computed_popularity"] = products["computed_popularity"].fillna(0.0)
        products["popularity_score"] = products.get("popularity_score", products["computed_popularity"])
        products["popularity_score"] = products["popularity_score"].fillna(products["computed_popularity"])
        return products.sort_values(["computed_popularity", "product_id"], ascending=[False, True])

    def get_users(self) -> list[str]:
        return list(self.user_item_matrix.index)

    def get_user_history(self, user_id: str) -> list[dict[str, object]]:
        history = self.interactions[self.interactions["user_id"] == user_id].merge(
            self.products[["product_id", "product_name", "category"]],
            on="product_id",
            how="left",
        )
        history = history.sort_values("timestamp", ascending=False)
        return history[
            ["product_id", "product_name", "category", "interaction_type", "interaction_score", "timestamp"]
        ].assign(timestamp=lambda df: df["timestamp"].astype(str)).to_dict(orient="records")

    def recommend(self, user_id: str, top_k: int = 5) -> tuple[list[Recommendation], str]:
        top_k = max(1, min(int(top_k), 50))
        if user_id not in self.user_item_matrix.index:
            return self._popular_recommendations(top_k), "popularity"

        user_based = self._user_based_scores(user_id)
        item_based = self._item_based_scores(user_id)
        combined = user_based.add(item_based, fill_value=0.0).sort_values(ascending=False)

        seen_products = set(self.interactions.loc[self.interactions["user_id"] == user_id, "product_id"])
        combined = combined.drop(labels=list(seen_products), errors="ignore")
        combined = combined[combined > 0]

        if combined.empty:
            return self._popular_recommendations(top_k, exclude=seen_products), "popularity"

        products_by_id = self.products.set_index("product_id")
        recommendations: list[Recommendation] = []
        for product_id, score in combined.head(top_k).items():
            if product_id not in products_by_id.index:
                continue
            product = products_by_id.loc[product_id]
            reason = (
                "Similar item to your previous interaction"
                if item_based.get(product_id, 0.0) >= user_based.get(product_id, 0.0)
                else "Similar users liked this product"
            )
            recommendations.append(
                Recommendation(
                    product_id=str(product_id),
                    product_name=str(product["product_name"]),
                    category=str(product["category"]),
                    score=round(float(score), 4),
                    reason=reason,
                )
            )

        if len(recommendations) < top_k:
            existing = {rec.product_id for rec in recommendations}.union(seen_products)
            recommendations.extend(self._popular_recommendations(top_k - len(recommendations), exclude=existing))
        return recommendations[:top_k], "hybrid_collaborative_filtering"

    def _user_based_scores(self, user_id: str) -> pd.Series:
        similarities = self.user_similarity.loc[user_id].drop(labels=[user_id], errors="ignore")
        if similarities.empty or np.isclose(similarities.sum(), 0.0):
            return pd.Series(dtype=float)
        weighted_scores = similarities @ self.user_item_matrix.loc[similarities.index]
        return pd.Series(weighted_scores, index=self.user_item_matrix.columns) / max(float(similarities.sum()), 1e-9)

    def _item_based_scores(self, user_id: str) -> pd.Series:
        user_vector = self.user_item_matrix.loc[user_id]
        interacted = user_vector[user_vector > 0]
        if interacted.empty:
            return pd.Series(dtype=float)
        item_scores = self.item_similarity.loc[interacted.index].T @ interacted
        return pd.Series(item_scores, index=self.item_similarity.columns) / max(float(interacted.sum()), 1e-9)

    def _popular_recommendations(self, top_k: int, exclude: set[str] | None = None) -> list[Recommendation]:
        exclude = exclude or set()
        rows = self.popular_products[~self.popular_products["product_id"].isin(exclude)].head(top_k)
        return [
            Recommendation(
                product_id=str(row.product_id),
                product_name=str(row.product_name),
                category=str(row.category),
                score=round(float(row.computed_popularity), 4),
                reason="Popular product fallback",
            )
            for row in rows.itertuples(index=False)
        ]
