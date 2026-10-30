# Basket · Retail Recommendation Lab

An explainable e-commerce recommendation engine built with **Python, Pandas and Scikit-Learn**, served by FastAPI and explored through a React dashboard.

The model learns from real historical purchases: customers with similar purchase patterns help rank products a customer has not bought before. Each personalized suggestion shows up to three strongest contributing customers and their cosine similarity. A chronological offline evaluation compares the model with a popularity baseline.

![Dashboard showing personalized recommendations and their supporting evidence](docs/screenshots/dashboard.png)

[Mobile preview](docs/screenshots/mobile.png)

## Run locally without Docker

Prerequisites: **Python 3.14** and native **PostgreSQL 16**. On macOS, download the PostgreSQL 16 build of [Postgres.app](https://postgresapp.com/downloads.html) into `~/Applications` or `/Applications`. On supported Homebrew installations, `brew install postgresql@16` also works. The launcher detects those binaries; `LOCAL_PG_BIN` supports another installation directory.

From the project root:

```bash
./scripts/local.sh          # Start PostgreSQL and FastAPI in this terminal
./scripts/local.sh status   # Check them from another terminal
./scripts/local.sh stop     # Stop the project's local services
```

Open **http://127.0.0.1:8000/docs** for the API and **http://127.0.0.1:8000/ready** for readiness. Press **Ctrl+C** in the launcher terminal to stop its services while retaining the database.

The launcher creates/reuses `.venv`, installs missing or changed pinned dependencies, reuses the prepared model, and trains only when artifacts are missing or `--retrain` is requested. It initializes a dedicated PostgreSQL cluster, applies migrations, seeds matching purchases, and starts FastAPI. Ordinary restarts do not retrain or duplicate purchases.

Runtime files are kept under gitignored **`.runtime/local/`**:

- `pgdata/`: persistent database files.
- `db-password` and `pgpass`: generated local credentials; keep these with the cluster.
- `api.log` and `postgres.log`: service logs.
- `state.json`, `owner.json` and `launcher.lock`: process/configuration ownership and duplicate-launch protection.

Both services bind to `127.0.0.1`. PostgreSQL defaults to **55433**, separate from Docker's **55432**. The script supplies its own database connection settings to migrations, seeding and the API. It does not use the Docker database or call Docker commands.

| Environment variable | Default / purpose |
| --- | --- |
| `LOCAL_API_PORT` | `8000` |
| `LOCAL_PG_PORT` | `55433` |
| `LOCAL_PG_BIN` | Auto-detected directory containing PostgreSQL 16 binaries |
| `LOCAL_PYTHON` | Project `.venv/bin/python`, otherwise Python 3.14 for venv creation; an explicit override should point to your prepared environment |
| `LOCAL_RUNTIME_DIR` | `.runtime/local/`; a separate dedicated directory can isolate another run |

The script refuses occupied ports or another project's runtime. If the Docker demo is already running, stop it first with `docker compose stop`, or choose a free API port:

```bash
LOCAL_API_PORT=8001 ./scripts/local.sh
./scripts/local.sh --retrain  # Explicitly regenerate/evaluate the model when needed
# Inspect request/server logs:
tail -f .runtime/local/api.log
```

An already running PostgreSQL instance in this project's cluster is reused and left running when that launcher exits. `stop` explicitly stops the project-local cluster. Unrelated services and existing database contents are preserved. An incomplete or mismatched cluster produces an actionable error instead of being automatically erased.

The frontend runs separately with Node 24:

```bash
cd frontend
npm ci
npm run dev
```

If using API port 8001 alongside the Docker demo, start a separate frontend port as well:

```bash
API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev -- --port 5174
```

## Run the complete demo with Docker

Prerequisites: Docker Desktop / Docker Engine with Compose, an internet connection for the first download, and available ports **5173**, **8000**, and **55432**.

```bash
./scripts/demo.sh
```

The script explicitly downloads the attributed dataset, cleans purchases, selects the neighborhood size, evaluates the model, saves a serving bundle, then starts PostgreSQL, migrations, database seeding, the API, and the built frontend. The first run takes longer because it downloads dependencies and the 23 MB workbook and trains the model.

- Dashboard: http://localhost:5173
- Interactive API documentation: http://localhost:8000/docs
- Readiness: http://localhost:8000/ready

Subsequent starts can reuse the prepared artifacts:

```bash
docker compose up -d --wait
# Stop containers while keeping purchases and logs:
docker compose down
```

The `retail_postgres_v2` volume is separate from the previous synthetic demo volume. Seeding refuses to overwrite an unrelated or mismatched dataset. No volume deletion is needed for normal setup.

## What the dashboard demonstrates

- Search and select an existing customer, or choose **New customer** to demonstrate cold start.
- Compare **Collaborative filtering** with **Popularity baseline** for the same customer.
- Request five or ten unseen products and expand **Why this recommendation?** to inspect actual contributing neighbors.
- Review purchase history, nearest customers, historical evaluation, popular products, and persisted request logs.
- Explore on desktop or mobile; loading, API failure, no-history and no-candidate states are handled explicitly.

Product monograms are visual placeholders, not photographs of source products. The source does not provide categories or images.

## Architecture

```mermaid
flowchart LR
    UCI[UCI workbook] --> Clean[Clean and audit purchases]
    Clean --> Eval[Chronological evaluation]
    Clean --> Fit[Fit sparse user model]
    Eval --> Bundle[Versioned model bundle]
    Fit --> Bundle
    Clean --> Seed[Transactional database seed]
    Seed --> PG[(PostgreSQL)]
    Bundle --> API[FastAPI]
    API --> PG
    UI[React dashboard] --> API
```

The offline pipeline owns data processing, parameter selection, evaluation and training. API startup validates the saved bundle and the database fingerprint. Requests never download data, retrain, or recalculate evaluation metrics. PostgreSQL stores catalog metadata, purchase histories, dataset identity and served recommendation logs.

### Recommendation algorithm

1. Count **distinct purchase invoices** per customer/product pair.
2. Transform counts with `log(1 + count)` and build a SciPy sparse matrix. A missing entry means unobserved preference, not a dislike.
3. L2-normalize each customer vector and find cosine nearest neighbors using Scikit-Learn.
4. Exclude the requesting customer and zero-similarity neighbors. Rank unseen products by the similarity-weighted average of neighbors' normalized purchase strengths.
5. Fill any remaining slots with popularity, ranked by distinct purchasing customers. The same seen-product exclusions apply to both methods.

Repeated purchases provide a stronger signal, while raw bulk quantities do not distort preference strength. Self exclusion and ID-based tie-breaking keep results deterministic. Only one customer's distances are computed at a time; a dense all-user or all-product similarity matrix is never stored. Exact neighbor search still scans the user population and is intended for this dataset scale.

**Scores are ranking signals, not purchase probabilities.** Popularity scores are distinct-buyer counts and have different units from collaborative scores. Each returned product identifies its source.

## Real dataset and cleaning

[UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online-retail) contains 541,909 invoice lines from a UK retailer between December 2010 and December 2011. Many customers are wholesalers. Attribution: **Chen, D. (2015). Online Retail. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33**. Dataset license: **CC BY 4.0**.

The pipeline verifies the original workbook's SHA-256, removes missing/blank identifiers or descriptions, invalid dates, cancellations, nonpositive/nonfinite quantity or price, non-merchandise stock codes, and exact duplicate lines. It then combines repeated lines within an invoice/product. Merchandise codes must have five digits with an optional one- or two-letter suffix; postage, fees, manual adjustments and vouchers are excluded.

Cleaning counts, hashes, source attribution and dates are recorded in `backend/models/model_manifest.json`. Returns are excluded as invalid positive-purchase signals; this is **not** a net-return or profit model. Source timestamps are kept as supplied local wall-clock times for chronological splitting; no precise source timezone is inferred.

Raw data, processed CSVs, and model binaries are ignored by Git and reproducibly rebuilt. Only small provenance and evaluation reports are committed. No click events, ratings, product categories, or online engagement results are invented.

## Evaluation

The task is **novel-product discovery for returning customers**, not repeat-purchase prediction.

| Stage | History available | Evaluation period |
| --- | --- | --- |
| Parameter selection | Before 1 November 2011 | November 2011 |
| Final offline test | Before 1 December 2011 | December 2011 through the source end |
| Serving demo | All cleaned purchases | Interactive exploration only |

Neighbor counts `{10, 25, 50}` compete on validation NDCG@10. The best configuration is locked, refitted through November, and tested on December. Exact validation ties prefer fewer neighbors.

Both methods rank the **full training catalog**, exclude already-purchased products, and use the same eligible customers and target products. Metrics are macro averages over returning customers with at least one previously unpurchased target in the training catalog. New customers, previously purchased targets and unavailable products are counted separately in the report. Coverage measures distinct recommended products divided by test-catalog size. Precision uses a denominator of ten even when fewer candidates are available.

<!-- RESULTS:START -->
| Metric | Collaborative filtering | Popularity |
| --- | ---: | ---: |
| Precision@10 | 0.041833 | 0.020518 |
| Recall@10 | 0.038960 | 0.021177 |
| MAP@10 | 0.027086 | 0.007925 |
| NDCG@10 | 0.055447 | 0.022933 |
| Catalog coverage | 0.161326 | 0.018899 |

Evaluated **502** of 614 December customers: 41 were new and 71 had no eligible discovery targets. The test catalog contains 3,651 products. Selected neighborhood: **50**. NDCG@10 improved **141.8% relative to popularity** on this offline cohort. Absolute scores remain modest: Precision@10 is 4.18%; this is a sparse discovery task, not a claim of high overall prediction accuracy.

The serving snapshot contains **4,334 customers**, **3,659 products**, and **386,326 purchase events**. Model version: `f24714941393cb5c`. See the [complete evaluation report](backend/reports/training_metrics.json) and [data/model manifest](backend/models/model_manifest.json).
<!-- RESULTS:END -->

These are **offline ranking metrics**. They do not measure engagement, click-through, conversion or revenue lift. Establishing those outcomes would require real impression/outcome logging and a controlled online experiment. The dashboard's evaluation remains the frozen historical report even though its serving model uses all history.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /recommend/{user_id}?top_k=5&strategy=collaborative` | Ranked suggestions, evidence, model version, request ID; logs the served result |
| `GET /recommend/{user_id}?strategy=popularity` | Popularity comparison with the same seen-item exclusions |
| `GET /users?q=123&limit=50` | Search customer IDs; limit up to 5,000 |
| `GET /users/{user_id}/history?limit=20` | Most recent purchases; limit up to 100 |
| `GET /users/{user_id}/neighbors?limit=5` | Most similar customers; at most ten and at most the fitted neighbor count |
| `GET /products/popular?top_k=5` | Store-wide favorites |
| `GET /model` | Dataset provenance, serving snapshot and artifact identity |
| `GET /metrics` | Frozen historical test report and baseline comparison |
| `GET /recommendation-logs?limit=10` | Latest served requests; limit up to 100 |
| `GET /health`, `GET /ready` | Liveness and database/model readiness |

Recommendation count must be between 1 and 50. Unknown customers receive popularity results and empty history/neighbors. Requests can return fewer products if the unseen catalog is exhausted. Customer IDs accept letters, digits, hyphens and underscores, up to 64 characters. Database failures return a clear HTTP 503 rather than a successful but unlogged recommendation.

```bash
curl 'http://localhost:8000/recommend/12347?top_k=5'
curl 'http://localhost:8000/recommend/NEW_CUSTOMER?top_k=5'
curl 'http://localhost:8000/metrics'
```

`/metrics` now returns explicit `collaborative`, `popularity`, `cohort` and protocol sections instead of the original unversioned four-number payload. The accompanying frontend uses this v2 contract. Recommendation responses retain their original core fields and add model/request identity and per-product evidence.

## Develop locally

Use **Python 3.14**, native **PostgreSQL 16**, and **Node 24** for the frontend. Start the backend/database with `./scripts/local.sh`, then run `npm ci` and `npm run dev` from `frontend/` in another terminal. See the native setup section above for installation, logs, process control and port overrides.

The frontend defaults to `/api`; Vite proxies to `http://127.0.0.1:8000` locally and `http://backend:8000` in Compose. `VITE_API_BASE_URL` can point to a different API when building; direct browser origins must also be allowed by backend CORS. `CORS_ORIGINS` is inherited by the local launcher. See `.env.example` for configuration examples.

To retrain, stop the local launcher and run `./scripts/local.sh --retrain`. Repeating training on identical source data, Python version and package versions keeps the model identity stable. Changing the processed dataset requires a matching fresh dedicated database; the seeder deliberately does not silently replace historical rows.

## Tests

Native launcher checks run from the project root:

```bash
.venv/bin/python -m pytest scripts/tests -q
# Include real native startup, Ctrl+C, retained data, restart and stop:
RUN_NATIVE_LOCAL_TESTS=1 .venv/bin/python -m pytest scripts/tests -q
```

The native integration case requires PostgreSQL 16 and an already prepared model. It uses temporary runtime files and free ports, leaving the normal local cluster alone. CI also exercises this path on Linux without a database container.

```bash
# From backend/, with the project environment active:
python -m pytest -q
# Include real PostgreSQL migrations (an isolated temporary schema is used):
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:55432/ecommerce_recommendations python -m pytest -q

# From frontend/, while the seeded API is running:
npm ci
npx playwright install chromium
npm run build
npm test
```

Backend tests use deterministic tiny purchases and never generate the full dataset. They cover cleaning, sparse weighting, hand-computed cosine scores, actual contribution evidence, deterministic exclusions/fallback, temporal splits, validation-only parameter selection, metrics, artifact identity, transactional seeding, API contracts and PostgreSQL migration preservation. Browser tests exercise customer search, evidence, baseline comparison, cold start, request races, error recovery, and desktop/mobile layouts against the real API.

Playwright's current bundled browsers require a supported host OS. On older macOS, `PLAYWRIGHT_CHROMIUM_EXECUTABLE` can select an existing compatible Chromium executable; the test runner stays on the current pinned version. CI uses the current bundled Linux browser and exercises the built frontend.

With the demo running, `node scripts/capture.mjs` from `frontend/` recreates the desktop and mobile README screenshots using the same browser configuration.

GitHub Actions runs unit/integration tests, trains the attributed dataset, migrates/seeds PostgreSQL, builds the frontend and runs browser tests. Actual test results are required before publishing changes.

## Read the code

Start with `backend/src/data_loader.py`, then `preprocessing.py`, `recommender.py`, `evaluate.py`, and `train_model.py`. Follow a request from `backend/app/api/recommendation_routes.py` through `services/recommendation_service.py` to the model and database. The dashboard entry point is `frontend/src/pages/RecommendationDashboard.jsx`.

Meaningful branches, mathematical operations and lifecycle boundaries have comments/docstrings explaining **why**, alongside named functions explaining what happens.

## Limitations

This is a local portfolio application with a historical snapshot, not a live storefront. There is no event-ingestion API, online model update, authentication or public hosting. A new customer needs behavior collection before collaborative filtering can personalize; a new product needs purchase evidence. Purchase history has exposure bias, and an unobserved product is not necessarily irrelevant. The wholesale-heavy source may not generalize to a different retailer. Exact neighbor search and the single-process model should be replaced or scaled for substantially larger populations.
