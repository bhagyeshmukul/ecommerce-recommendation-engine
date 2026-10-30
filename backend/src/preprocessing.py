"""Turn purchase histories into compact user preference vectors."""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.preprocessing import normalize


@dataclass
class InteractionMatrix:
    """The ordered ID maps are as important as the matrix values when serving."""

    values: csr_matrix
    normalized: csr_matrix
    users: list[str]
    products: list[str]


def create_user_item_matrix(events: pd.DataFrame) -> InteractionMatrix:
    """Use log(1 + distinct invoices) to reflect repeats without wholesale bias."""
    required = {"user_id", "product_id", "invoice_id"}
    if required - set(events.columns) or events.empty:
        raise ValueError(
            "Nonempty user_id/product_id/invoice_id purchases are required"
        )
    if events[list(required)].isna().any().any():
        raise ValueError("Purchase identifiers cannot be missing")
    grouped = events.groupby(["user_id", "product_id"])["invoice_id"].nunique()
    users = sorted(events.user_id.unique().tolist())
    products = sorted(events.product_id.unique().tolist())
    user_lookup = {value: index for index, value in enumerate(users)}
    product_lookup = {value: index for index, value in enumerate(products)}
    rows = [user_lookup[user] for user, _ in grouped.index]
    columns = [product_lookup[product] for _, product in grouped.index]
    values = csr_matrix(
        (np.log1p(grouped.to_numpy(dtype=float)), (rows, columns)),
        shape=(len(users), len(products)),
    )
    return InteractionMatrix(
        values, normalize(values, norm="l2", axis=1, copy=True).tocsr(), users, products
    )
