from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


CATEGORIES = ["Electronics", "Home", "Beauty", "Sports", "Books", "Fashion", "Grocery", "Toys"]

DOMAIN_CATALOG = {
    "electronics": {
        "categories": ["Phones", "Audio", "Computers", "Gaming", "Cameras"],
        "nouns": ["Headphones", "Tablet", "Keyboard", "Camera", "Speaker", "Monitor"],
    },
    "fashion": {
        "categories": ["Shoes", "Outerwear", "Accessories", "Denim", "Athleisure"],
        "nouns": ["Sneakers", "Jacket", "Watch", "Jeans", "Hoodie", "Sunglasses"],
    },
    "grocery": {
        "categories": ["Snacks", "Beverages", "Pantry", "Organic", "Breakfast"],
        "nouns": ["Coffee", "Granola", "Olive Oil", "Tea", "Protein Bar", "Cereal"],
    },
    "beauty": {
        "categories": ["Skincare", "Haircare", "Makeup", "Fragrance", "Wellness"],
        "nouns": ["Serum", "Shampoo", "Lipstick", "Perfume", "Moisturizer", "Cleanser"],
    },
    "home": {
        "categories": ["Kitchen", "Decor", "Furniture", "Storage", "Lighting"],
        "nouns": ["Mixer", "Lamp", "Chair", "Shelf", "Cookware", "Cushion"],
    },
    "sports": {
        "categories": ["Fitness", "Outdoor", "Cycling", "Yoga", "Team Sports"],
        "nouns": ["Yoga Mat", "Dumbbell", "Helmet", "Backpack", "Football", "Bottle"],
    },
    "books": {
        "categories": ["Fiction", "Business", "Technology", "Self Help", "Education"],
        "nouns": ["Novel", "Workbook", "Guide", "Manual", "Biography", "Cookbook"],
    },
    "marketplace": {
        "categories": ["Deals", "Premium", "Essentials", "Subscriptions", "Bundles"],
        "nouns": ["Bundle", "Starter Kit", "Gift Box", "Membership", "Sampler", "Pack"],
    },
}

ADJECTIVES = ["Pro", "Lite", "Eco", "Max", "Smart", "Urban", "Prime", "Flex", "Daily", "Elite"]
NOUNS = ["Headphones", "Backpack", "Mixer", "Sneakers", "Serum", "Notebook", "Bottle", "Lamp"]


def generate_synthetic_ecommerce_data(
    n_users: int = 80,
    n_products: int = 60,
    min_interactions: int = 6,
    max_interactions: int = 18,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create realistic enough e-commerce interactions for a portfolio project."""
    rng = np.random.default_rng(random_state)

    users = pd.DataFrame({"user_id": [f"U{idx:04d}" for idx in range(1, n_users + 1)]})
    products = pd.DataFrame(
        {
            "product_id": [f"P{idx:04d}" for idx in range(1, n_products + 1)],
            "product_name": [
                f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)} {idx:02d}"
                for idx in range(1, n_products + 1)
            ],
            "category": rng.choice(CATEGORIES, size=n_products),
        }
    )

    rows: list[dict[str, object]] = []
    base_date = pd.Timestamp("2026-01-01")
    interaction_weights = {"view": 1.0, "click": 2.0, "rating": 3.0, "purchase": 5.0}

    for user_id in users["user_id"]:
        preferred_categories = rng.choice(CATEGORIES, size=2, replace=False)
        candidate_products = products[products["category"].isin(preferred_categories)]["product_id"].to_numpy()
        if len(candidate_products) < min_interactions:
            candidate_products = products["product_id"].to_numpy()

        n_events = int(rng.integers(min_interactions, max_interactions + 1))
        chosen_products = rng.choice(candidate_products, size=min(n_events, len(candidate_products)), replace=False)

        for product_id in chosen_products:
            interaction_type = str(rng.choice(["view", "click", "rating", "purchase"], p=[0.35, 0.30, 0.15, 0.20]))
            rows.append(
                {
                    "user_id": user_id,
                    "product_id": product_id,
                    "interaction_type": interaction_type,
                    "interaction_score": interaction_weights[interaction_type],
                    "timestamp": base_date + pd.Timedelta(days=int(rng.integers(0, 120))),
                }
            )

    interactions = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    popularity = (
        interactions.groupby("product_id")["interaction_score"]
        .sum()
        .rename("popularity_score")
        .reset_index()
    )
    products = products.merge(popularity, on="product_id", how="left").fillna({"popularity_score": 0.0})
    return users, products, interactions


def generate_domain_dataset(
    domain: str,
    n_users: int = 90,
    n_products: int = 70,
    min_interactions: int = 8,
    max_interactions: int = 22,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate one domain-specific e-commerce behavior dataset."""
    if domain not in DOMAIN_CATALOG:
        raise ValueError(f"Unsupported domain '{domain}'. Choose from: {sorted(DOMAIN_CATALOG)}")

    rng = np.random.default_rng(random_state)
    config = DOMAIN_CATALOG[domain]
    users = pd.DataFrame(
        {
            "user_id": [f"{domain[:3].upper()}_U{idx:04d}" for idx in range(1, n_users + 1)],
            "source_domain": domain,
        }
    )
    products = pd.DataFrame(
        {
            "product_id": [f"{domain[:3].upper()}_P{idx:04d}" for idx in range(1, n_products + 1)],
            "product_name": [
                f"{rng.choice(ADJECTIVES)} {rng.choice(config['nouns'])} {idx:03d}"
                for idx in range(1, n_products + 1)
            ],
            "category": rng.choice(config["categories"], size=n_products),
            "source_domain": domain,
        }
    )

    interaction_weights = {
        "view": 1.0,
        "click": 2.0,
        "add_to_cart": 3.5,
        "rating": 4.0,
        "wishlist": 3.0,
        "purchase": 6.0,
    }
    interaction_types = list(interaction_weights)
    interaction_probabilities = [0.28, 0.24, 0.14, 0.10, 0.10, 0.14]
    base_date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(random_state % 30))
    rows: list[dict[str, object]] = []

    for user_id in users["user_id"]:
        preferred_categories = rng.choice(config["categories"], size=2, replace=False)
        candidate_products = products[products["category"].isin(preferred_categories)]["product_id"].to_numpy()
        if len(candidate_products) < min_interactions:
            candidate_products = products["product_id"].to_numpy()

        n_events = int(rng.integers(min_interactions, max_interactions + 1))
        chosen_products = rng.choice(candidate_products, size=min(n_events, len(candidate_products)), replace=False)
        for product_id in chosen_products:
            interaction_type = str(rng.choice(interaction_types, p=interaction_probabilities))
            recency_boost = 1.0 + float(rng.uniform(0, 0.2))
            rows.append(
                {
                    "user_id": user_id,
                    "product_id": product_id,
                    "interaction_type": interaction_type,
                    "interaction_score": round(interaction_weights[interaction_type] * recency_boost, 3),
                    "timestamp": base_date + pd.Timedelta(days=int(rng.integers(0, 150))),
                    "source_domain": domain,
                }
            )

    interactions = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    popularity = (
        interactions.groupby("product_id")["interaction_score"]
        .sum()
        .rename("popularity_score")
        .reset_index()
    )
    products = products.merge(popularity, on="product_id", how="left").fillna({"popularity_score": 0.0})
    return users, products, interactions


def generate_multi_domain_ecommerce_data(
    domains: list[str] | None = None,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create a composite training dataset across several e-commerce verticals."""
    domains = domains or list(DOMAIN_CATALOG)
    users_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    interaction_frames: list[pd.DataFrame] = []

    for offset, domain in enumerate(domains):
        users, products, interactions = generate_domain_dataset(
            domain=domain,
            random_state=random_state + offset * 17,
        )
        users_frames.append(users)
        product_frames.append(products)
        interaction_frames.append(interactions)

    return (
        pd.concat(users_frames, ignore_index=True),
        pd.concat(product_frames, ignore_index=True),
        pd.concat(interaction_frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True),
    )


def load_or_generate_dataset(
    data_dir: str | Path | None = None,
    multi_domain: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data_path = Path(data_dir or Path(__file__).resolve().parents[1] / "data")
    users_file = data_path / "users.csv"
    products_file = data_path / "products.csv"
    interactions_file = data_path / "interactions.csv"

    if users_file.exists() and products_file.exists() and interactions_file.exists():
        return (
            pd.read_csv(users_file),
            pd.read_csv(products_file),
            pd.read_csv(interactions_file, parse_dates=["timestamp"]),
        )

    users, products, interactions = (
        generate_multi_domain_ecommerce_data() if multi_domain else generate_synthetic_ecommerce_data()
    )
    data_path.mkdir(parents=True, exist_ok=True)
    users.to_csv(users_file, index=False)
    products.to_csv(products_file, index=False)
    interactions.to_csv(interactions_file, index=False)
    return users, products, interactions
