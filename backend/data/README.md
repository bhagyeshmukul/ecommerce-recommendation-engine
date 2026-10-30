# UCI Online Retail purchases

Source: https://archive.ics.uci.edu/dataset/352/online-retail

Citation: Chen, D. (2015). Online Retail. UCI Machine Learning Repository. DOI: https://doi.org/10.24432/C5BW33

License: Creative Commons Attribution 4.0 International (CC BY 4.0).

The original workbook contains 541,909 invoice lines dated 2010-12-01 through 2011-12-09. It records purchases, cancellations, quantities, prices and customer IDs. It does not supply click events, ratings, product categories, or engagement experiments.

Run `python -m src.train_model` from `backend/` to download, verify, clean, evaluate and train. Alternatively, `./scripts/demo.sh` runs the full Docker workflow from the project root.

Generated and gitignored directories:

- `raw/online_retail.xlsx`: original source workbook. Expected SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.
- `processed/purchases.csv`: cleaned invoice/product purchase events.

The workbook is pinned by checksum. If the network is unavailable, download the original workbook from the cited source and place it at `raw/online_retail.xlsx`; the same checksum validation applies. Never substitute the prior synthetic CSVs for this dataset.

Cleaning rules and removal counts are in `src/data_loader.py` and the public `models/model_manifest.json`. Model files live under `models/bundle/`, while the committed report in `reports/training_metrics.json` documents the chronological evaluation.

Older synthetic CSVs may still exist in an existing local checkout. The new pipeline never reads them, and they remain ignored. Product descriptions and anonymized customer IDs are retained from the source with attribution.
