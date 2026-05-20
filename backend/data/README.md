# E-commerce Training Data

The training pipeline generates a composite e-commerce dataset covering several retail domains:

- Electronics
- Fashion
- Grocery
- Beauty
- Home
- Sports
- Books
- Marketplace bundles and deals

Generated files:

- `users.csv`
- `products.csv`
- `interactions.csv`

Each interaction includes `view`, `click`, `add_to_cart`, `wishlist`, `rating`, and `purchase` events with weighted interaction scores. The generated CSV files are intentionally ignored by Git so the repository stays lightweight. Recreate them with:

```bash
cd backend
python -m src.train_model --regenerate
```

Public datasets that can be adapted to the same schema later:

- RetailRocket recommender dataset
- Amazon product reviews
- Instacart market basket dataset
- UCI Online Retail
- Brazilian E-commerce Public Dataset by Olist
- H&M personalized fashion recommendations
