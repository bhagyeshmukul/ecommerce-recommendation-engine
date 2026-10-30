"""Check purchase weighting and sparse representation using hand-computed values."""

import numpy as np
import pandas as pd
import pytest
from scipy.sparse import issparse
from src.preprocessing import create_user_item_matrix


def test_repeat_invoices_count_once_and_quantity_does_not_weight(purchases):
    repeated = purchases.iloc[[0]].copy()
    repeated["quantity"] = 10000
    new_invoice = repeated.assign(invoice_id="NEW")
    matrix = create_user_item_matrix(pd.concat([purchases, repeated, new_invoice]))
    assert issparse(matrix.values)
    assert matrix.values[0, 0] == pytest.approx(np.log1p(2))
    assert matrix.values[0, 1] == pytest.approx(np.log1p(1))
    assert np.linalg.norm(matrix.normalized[0].toarray()) == pytest.approx(1)
    assert matrix.values[0, 4] == 0


def test_empty_or_missing_ids_rejected(purchases):
    with pytest.raises(ValueError):
        create_user_item_matrix(purchases.iloc[:0])
    with pytest.raises(ValueError):
        create_user_item_matrix(purchases.assign(user_id=None))
