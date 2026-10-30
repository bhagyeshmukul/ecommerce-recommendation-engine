"""Explainable user-based collaborative filtering with cosine nearest neighbors.

For each unseen item j, score(u,j) = sum(sim(u,v) * normalized_purchase(v,j))
                                     / sum(sim(u,v)).
Scores are ranking signals, not probabilities. Popularity fills missing candidates.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from src.preprocessing import create_user_item_matrix


@dataclass(frozen=True)
class Recommendation:
    product_id: str
    product_name: str
    category: str | None
    score: float
    reason: str
    source: str = "user_cosine"
    supporting_users: int = 0
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class EcommerceRecommender:
    """Fit once, query many times. No dense user-user or item-item matrix is stored."""

    def __init__(
        self, interactions: pd.DataFrame, products: pd.DataFrame, n_neighbors: int = 25
    ):
        if n_neighbors < 1:
            raise ValueError("n_neighbors must be positive")
        self.matrix = create_user_item_matrix(interactions)
        self.n_neighbors = n_neighbors
        self.user_lookup = {user: i for i, user in enumerate(self.matrix.users)}
        self.product_lookup = {
            product: i for i, product in enumerate(self.matrix.products)
        }
        self.products = (
            products.set_index("product_id").loc[self.matrix.products].copy()
        )
        self.index = NearestNeighbors(metric="cosine", algorithm="brute", n_jobs=1).fit(
            self.matrix.normalized
        )
        # Distinct buyers resist bulk quantity distortion and form the common baseline.
        self.popularity = np.asarray((self.matrix.values > 0).sum(axis=0)).ravel()
        self.popular_order = sorted(
            range(len(self.matrix.products)),
            key=lambda i: (-self.popularity[i], self.matrix.products[i]),
        )
        self.model_version = "unversioned"

    def get_users(self) -> list[str]:
        return self.matrix.users.copy()

    def seen_indices(self, user_id: str) -> set[int]:
        if user_id not in self.user_lookup:
            return set()
        return set(self.matrix.values[self.user_lookup[user_id]].indices.tolist())

    def neighbors(self, user_id: str, limit: int | None = None) -> list[dict]:
        """Remove self by identity; identical vectors can have a different tie order.

        Query all distances for one user, then sort by similarity and stable ID.
        This guarantees deterministic ties without storing an O(users²) matrix.
        """
        if user_id not in self.user_lookup:
            return []
        row = self.user_lookup[user_id]
        distances, indices = self.index.kneighbors(
            self.matrix.normalized[row], n_neighbors=len(self.matrix.users)
        )
        # Clip once as an array rather than invoking NumPy for every scalar.
        similarities = np.clip(1 - distances[0], 0, 1)
        candidates = [
            (int(i), float(similarity))
            for i, similarity in zip(indices[0], similarities)
            if int(i) != row and similarity > 1e-12
        ]
        candidates.sort(
            key=lambda pair: (-round(pair[1], 12), self.matrix.users[pair[0]])
        )
        selected = candidates[: min(limit or self.n_neighbors, self.n_neighbors)]
        return [
            {"user_id": self.matrix.users[i], "similarity": similarity}
            for i, similarity in selected
        ]

    def _recommendation(
        self,
        index: int,
        score: float,
        source: str,
        evidence: list[dict] | None = None,
        supporting_users: int = 0,
    ) -> Recommendation:
        product_id = self.matrix.products[index]
        product = self.products.loc[product_id]
        evidence = evidence or []
        return Recommendation(
            product_id=product_id,
            product_name=str(product.product_name),
            category=None,
            score=round(float(score), 6),
            reason=(
                f"Purchased by {supporting_users} similar customer{'s' if supporting_users != 1 else ''}"
                if source == "user_cosine"
                else "Popular with customers across the store"
            ),
            source=source,
            supporting_users=supporting_users,
            evidence=evidence,
        )

    def popular_recommendations(
        self, top_k: int, exclude: set[int] | None = None
    ) -> list[Recommendation]:
        """Popularity scores are buyer counts; do not compare them with cosine scores."""
        excluded = exclude or set()
        chosen = [i for i in self.popular_order if i not in excluded][:top_k]
        return [
            self._recommendation(i, self.popularity[i], "popularity") for i in chosen
        ]

    def recommend(
        self, user_id: str, top_k: int = 5, strategy: str = "collaborative"
    ) -> tuple[list[Recommendation], str]:
        if not 1 <= top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")
        if strategy not in {"collaborative", "popularity"}:
            raise ValueError("Unknown strategy")
        seen = self.seen_indices(user_id)
        neighbors = self.neighbors(user_id) if strategy == "collaborative" else []
        if not neighbors:
            return self.popular_recommendations(top_k, seen), "popularity"
        rows = [self.user_lookup[neighbor["user_id"]] for neighbor in neighbors]
        similarities = np.array([neighbor["similarity"] for neighbor in neighbors])
        contributions = (
            self.matrix.normalized[rows].multiply(similarities[:, None]).tocsr()
        )
        scores = np.asarray(contributions.sum(axis=0)).ravel() / similarities.sum()
        candidates = [int(i) for i in np.flatnonzero(scores > 0) if int(i) not in seen]
        candidates.sort(
            key=lambda i: (-round(float(scores[i]), 12), self.matrix.products[i])
        )
        recommendations = []
        for i in candidates[:top_k]:
            column = contributions[:, i].toarray().ravel()
            supporters = np.flatnonzero(column > 0)
            best = sorted(
                supporters, key=lambda n: (-column[n], neighbors[n]["user_id"])
            )[:3]
            evidence = [
                {
                    "user_id": neighbors[n]["user_id"],
                    "similarity": round(neighbors[n]["similarity"], 6),
                    "contribution": round(float(column[n] / similarities.sum()), 6),
                }
                for n in best
            ]
            recommendations.append(
                self._recommendation(
                    i, scores[i], "user_cosine", evidence, len(supporters)
                )
            )
        chosen = {self.product_lookup[rec.product_id] for rec in recommendations}
        recommendations.extend(
            self.popular_recommendations(top_k - len(recommendations), seen | chosen)
        )
        actual_strategy = "user_cosine" if candidates else "popularity"
        return recommendations, actual_strategy
