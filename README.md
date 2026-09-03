# Product Service

REST microservice for an e-commerce product catalogue: products, a hierarchical category tree, and filterable search on `GET /api/v1/products`.

Stack: FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16.

The why behind each design choice is in [docs/design.md](docs/design.md). The implementation sequence is in [docs/plan.md](docs/plan.md).

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose (Rancher Desktop or Docker Desktop). Compose publishes Postgres on host port **5433** so it does not collide with a local install on 5432.

## Setup

```bash
cp .env.example .env
uv sync
docker compose up -d db
uv run alembic upgrade head
uv run python -m scripts.seed
uv run uvicorn app.main:app --reload
```

Health check: `curl http://localhost:8000/health`  
OpenAPI: http://localhost:8000/docs

## Tests

```bash
uv run pytest
uv run pytest tests/unit -q          # no database required
uv run ruff check . && uv run ruff format --check .
uv run mypy app
```

From a clean database volume:

```bash
docker compose down -v
docker compose up -d db
uv run alembic upgrade head
uv run python -m scripts.seed
uv run pytest
```

## Search examples

These match the seed data.

```bash
# title or description contains "phone", cheapest first
curl "http://localhost:8000/api/v1/products?q=phone&sort=price"

# everything under Electronics, including nested subcategories
curl "http://localhost:8000/api/v1/products?category_id=1"

# directly in Phones, ignoring Smartphones beneath it
curl "http://localhost:8000/api/v1/products?category_id=2&include_descendants=false"

# mid-range phones under Electronics
curl "http://localhost:8000/api/v1/products?q=phone&category_id=1&price_min=100&price_max=500"

# exact SKU
curl "http://localhost:8000/api/v1/products?sku=smart-1"
curl "http://localhost:8000/api/v1/products/by-sku/SMART-1"
```

Filters combine with AND. An unknown query parameter is a `422`, not a silently ignored filter.

## Category listing examples

```bash
# Roots only (categories whose parent_id is NULL)
curl "http://localhost:8000/api/v1/categories?filter_parent=true"

# Direct children under a parent
curl "http://localhost:8000/api/v1/categories?parent_id=1"
```

## What is deliberately out of scope

Auth, image upload, multi-currency, inventory, variants, soft delete, and full-text relevance ranking. See the non-goals table in [docs/design.md](docs/design.md).
