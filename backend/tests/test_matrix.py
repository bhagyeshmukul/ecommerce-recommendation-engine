import pandas as pd

from src.preprocessing import create_user_item_matrix


def test_user_item_matrix_creation():
    interactions = pd.DataFrame(
        [
            {"user_id": "U1", "product_id": "P1", "interaction_type": "view", "interaction_score": 1, "timestamp": "2026-01-01"},
            {"user_id": "U1", "product_id": "P1", "interaction_type": "click", "interaction_score": 2, "timestamp": "2026-01-02"},
            {"user_id": "U2", "product_id": "P2", "interaction_type": "purchase", "interaction_score": 5, "timestamp": "2026-01-03"},
        ]
    )

    matrix = create_user_item_matrix(interactions)

    assert matrix.loc["U1", "P1"] == 3
    assert matrix.loc["U2", "P2"] == 5
    assert matrix.loc["U1", "P2"] == 0
