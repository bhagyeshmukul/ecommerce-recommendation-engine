from __future__ import annotations

import argparse
from pathlib import Path

from src.data_loader import DOMAIN_CATALOG, generate_multi_domain_ecommerce_data, load_or_generate_dataset
from src.evaluate import evaluate_recommender
from src.recommender import EcommerceRecommender
from src.utils import save_model, write_json_report


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "models" / "ecommerce_recommender.joblib"
DEFAULT_METRICS_PATH = ROOT / "reports" / "training_metrics.json"
DEFAULT_MANIFEST_PATH = ROOT / "models" / "model_manifest.json"


def train_model(
    output_path: Path = DEFAULT_MODEL_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    regenerate: bool = False,
) -> dict[str, object]:
    if regenerate:
        users, products, interactions = generate_multi_domain_ecommerce_data()
        data_dir = ROOT / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        users.to_csv(data_dir / "users.csv", index=False)
        products.to_csv(data_dir / "products.csv", index=False)
        interactions.to_csv(data_dir / "interactions.csv", index=False)
    else:
        users, products, interactions = load_or_generate_dataset()

    recommender = EcommerceRecommender(interactions=interactions, products=products)
    metrics = evaluate_recommender(interactions=interactions, products=products, k=5)
    save_model(recommender, output_path)
    write_json_report(metrics, metrics_path)

    manifest: dict[str, object] = {
        "model_type": "hybrid_user_item_collaborative_filtering",
        "artifact": str(output_path.relative_to(ROOT)),
        "metrics_report": str(metrics_path.relative_to(ROOT)),
        "dataset": {
            "users": int(users["user_id"].nunique()),
            "products": int(products["product_id"].nunique()),
            "interactions": int(len(interactions)),
            "domains": sorted(DOMAIN_CATALOG),
        },
        "metrics": metrics,
    }
    write_json_report(manifest, manifest_path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and persist the e-commerce recommendation model.")
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--regenerate", action="store_true", help="Regenerate the composite dataset before training.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    training_manifest = train_model(
        output_path=args.output,
        metrics_path=args.metrics,
        manifest_path=args.manifest,
        regenerate=args.regenerate,
    )
    print(training_manifest)
