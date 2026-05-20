# E-commerce Recommendation Engine

A production-style full-stack recommendation system that serves personalized product recommendations from a FastAPI backend and visualizes them in a React dashboard. The project includes collaborative filtering, cold-start fallback logic, evaluation metrics, PostgreSQL logging, Alembic migrations, Docker Compose, and pytest coverage.

## Business Problem

E-commerce teams need to increase product discovery, conversion, and repeat engagement. A recommendation engine turns user behavior such as views, clicks, ratings, and purchases into ranked product suggestions that can be used on home pages, product detail pages, email campaigns, and personalized storefronts.

## Recommendation Systems

Recommendation systems estimate which items a user is likely to prefer. This project uses collaborative filtering, which learns from patterns across users and products instead of relying only on manually defined rules.

## Collaborative Filtering

The backend builds a user-item interaction matrix where rows are users, columns are products, and values are weighted interaction scores. Purchases receive more weight than clicks, and clicks receive more weight than views. The recommender combines:

- User-based collaborative filtering: similar users liked this product.
- Item-based collaborative filtering: this product is similar to something the user already interacted with.
- Popularity fallback: cold-start users receive high-engagement products.

## Cosine Similarity

Cosine similarity measures the angle between two vectors. In this project, user vectors represent product interactions and item vectors represent users who interacted with each product. Higher cosine similarity means two users or products have more similar behavior patterns.

## Cold Start

Cold-start users have no historical interactions, so collaborative filtering cannot infer preferences. The API detects unknown users and returns popularity-based recommendations with the reason `Popular product fallback`.

## Dataset

The project generates a realistic synthetic e-commerce dataset with:

- Users
- Products
- Product categories
- Views, clicks, ratings, and purchases
- Weighted interaction scores
- Timestamps

Generated CSV files are stored under `backend/data/` at runtime and ignored by Git.

## Architecture

```text
React + Vite Dashboard
        |
        | Axios
        v
FastAPI Recommendation API
        |
        | SQLAlchemy ORM
        v
PostgreSQL

ML pipeline:
data_loader -> preprocessing -> recommender -> evaluate -> API service
```

## Database And Migrations

PostgreSQL is managed with Docker Compose. SQLAlchemy stores ORM model definitions in `backend/app/db/models.py`, connection logic in `backend/app/db/database.py`, and session lifecycle in `backend/app/db/session.py`.

Schema creation is handled by Alembic only. The application does not rely on `Base.metadata.create_all()` for production schema creation.

Alembic creates:

- `users`
- `products`
- `user_interactions`
- `recommendation_logs`

The backend container runs:

```bash
alembic upgrade head
python -m src.seed_database
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### `GET /recommend/{user_id}?top_k=5`

Returns personalized recommendations and logs the request to PostgreSQL.

```json
{
  "user_id": "U0001",
  "recommended_products": [
    {
      "product_id": "P0012",
      "product_name": "Smart Headphones 12",
      "category": "Electronics",
      "score": 4.82,
      "reason": "Similar users liked this product"
    }
  ],
  "recommendation_strategy": "hybrid_collaborative_filtering"
}
```

### `GET /users`

Returns available user IDs.

### `GET /products/popular`

Returns popular products for fallback and dashboard display.

### `GET /users/{user_id}/history`

Returns recent user interactions.

### `GET /metrics`

Returns `precision_at_k`, `recall_at_k`, `map_at_k`, and `coverage`.

### `GET /recommendation-logs`

Returns latest recommendation requests logged in PostgreSQL.

## Frontend

The React dashboard includes:

- User selector
- Recommended product cards
- Recommendation score and reason
- User interaction history
- Popular products
- Metrics chart with Recharts
- Latest recommendation logs table
- Loading and error states

Screenshot placeholders:

```text
docs/screenshots/dashboard.png
docs/screenshots/recommendation-cards.png
docs/screenshots/logs-table.png
```

## Run With Docker Compose

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

## Run Backend Locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_recommendations
alembic upgrade head
python -m src.seed_database
uvicorn app.main:app --reload
```

## Run Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

For local frontend calls directly to the backend:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Run Alembic Manually

```bash
cd backend
alembic upgrade head
alembic current
alembic history
```

Create a new migration:

```bash
alembic revision -m "describe change"
```

## Run Tests

```bash
cd backend
pytest
```

Tests cover matrix creation, cosine similarity, recommendation output, cold-start fallback, FastAPI endpoints, database logging, and recommendation logs.

## Project Structure

```text
backend/
  app/
    api/
    db/
    schemas/
    services/
  src/
  tests/
  alembic/
frontend/
  src/
docker-compose.yml
README.md
```

## Resume Bullet Points

- Built an end-to-end recommendation engine using FastAPI, Scikit-Learn, PostgreSQL, Alembic, React, and Docker Compose.
- Implemented hybrid collaborative filtering with user-based and item-based cosine similarity plus cold-start popularity fallback.
- Designed production-style API endpoints with SQLAlchemy logging and Alembic-managed PostgreSQL migrations.
- Created a React analytics dashboard showing recommendations, user history, model metrics, popular products, and request logs.
- Added pytest coverage for ML matrix generation, similarity computation, recommendations, API behavior, and database logging.

## Interview Explanation

This project demonstrates how to move recommendation logic from a notebook into a service-oriented application. The ML pipeline creates a user-item matrix, computes cosine similarity, ranks unseen products, explains recommendation reasons, evaluates ranking quality, and exposes the result through FastAPI. PostgreSQL stores recommendation request logs for observability, while Alembic manages schema changes in a repeatable deployment workflow.

## Interview Questions And Answers

**Q: Why use collaborative filtering?**  
A: It captures behavioral patterns across users and products without requiring deep product metadata.

**Q: How do you avoid recommending products a user already interacted with?**  
A: The recommender filters seen product IDs before returning the top ranked items.

**Q: How do you handle a new user?**  
A: Unknown users receive popularity-based recommendations until enough behavior is collected.

**Q: Why cosine similarity?**  
A: It compares interaction vectors by direction, which works well for sparse user-item preference patterns.

**Q: What is coverage?**  
A: Coverage measures how much of the catalog appears in recommendations. It helps detect systems that over-recommend only a few popular items.

**Q: Why use Alembic?**  
A: Alembic provides versioned, repeatable schema migrations, which are safer and more auditable than ad hoc table creation.

**Q: How would you improve this in production?**  
A: Add scheduled model training, feature stores, offline ranking evaluation, A/B testing, monitoring, authentication, request tracing, and a real event ingestion pipeline.
