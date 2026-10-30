"""Offline entry point: download → clean → validate → test → fit serving bundle."""

from __future__ import annotations
import argparse
import importlib.metadata
import json
import platform
from pathlib import Path

from src.data_loader import (
    DATA_DIR,
    ROOT,
    catalog_from_events,
    prepare_dataset,
    sha256_file,
)
from src.evaluate import evaluate_recommender
from src.recommender import EcommerceRecommender
from src.utils import content_id, save_model, write_json_report

BUNDLE_DIR = ROOT / "models" / "bundle"


def train_model(data_dir: Path = DATA_DIR, bundle_dir: Path = BUNDLE_DIR) -> dict:
    """One bundle binds a real dataset, serving model and historical test report."""
    events, dataset = prepare_dataset(data_dir)
    print(
        f"Cleaned {len(events):,} purchase events from {dataset['quality']['raw_rows']:,} source rows",
        flush=True,
    )
    metrics, neighbors = evaluate_recommender(events)
    versions = {
        name: importlib.metadata.version(name)
        for name in ["pandas", "numpy", "scipy", "scikit-learn", "joblib"]
    }
    identity = {
        "dataset_sha256": dataset["dataset_sha256"],
        "algorithm": "user_cosine_knn_v1",
        "neighbors": neighbors,
        "versions": versions,
        "python": platform.python_version(),
    }
    version = content_id(identity)
    model = EcommerceRecommender(events, catalog_from_events(events), neighbors)
    model.model_version = version
    bundle_dir.mkdir(parents=True, exist_ok=True)
    save_model(model, bundle_dir / "recommender.joblib")
    metrics.update(
        {"model_version": version, "dataset_sha256": dataset["dataset_sha256"]}
    )
    write_json_report(metrics, bundle_dir / "evaluation.json")
    manifest = {
        "model_version": version,
        "identity": identity,
        "dataset": dataset,
        "serving": {
            "fit_on": "all_cleaned_history",
            "history_end": dataset["date_end"],
            "users": len(model.matrix.users),
            "products": len(model.matrix.products),
            "neighbors": neighbors,
            "weight": "log1p(distinct purchase invoices), L2 normalized",
        },
        "files": {
            filename: sha256_file(bundle_dir / filename)
            for filename in ["recommender.joblib", "evaluation.json"]
        },
    }
    # Write the manifest last: its checksums identify the complete bundle.
    write_json_report(manifest, bundle_dir / "manifest.json")
    write_json_report(manifest, ROOT / "models" / "model_manifest.json")
    write_json_report(metrics, ROOT / "reports" / "training_metrics.json")
    print(
        json.dumps(
            {
                "model_version": version,
                "selected_neighbors": neighbors,
                "test": metrics["collaborative"],
                "baseline": metrics["popularity"],
                "cohort": metrics["cohort"],
            },
            indent=2,
        ),
        flush=True,
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--bundle-dir", type=Path, default=BUNDLE_DIR)
    args = parser.parse_args()
    train_model(args.data_dir, args.bundle_dir)
