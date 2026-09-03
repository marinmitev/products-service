# Product Service — Implementation Plan

Derived from `docs/design.md` (approved, all five open-question defaults accepted). Tasks run strictly in order; each is one commit and leaves the service runnable.

## Summary

| # | Task | Size | Migration | Status |
|---|---|---|---|---|
| T1 | Skeleton, config, Docker Compose, `/health` | M | – | [x] |
| T2 | Models, Alembic, first migration, indexes | M | yes | [x] |
| T3 | Category CRUD, cycle prevention, delete guards | M | – | [x] |
| T4 | Product CRUD | M | – | [x] |
| T5 | Search: filters, subtree, sorting, pagination | L | yes (trigram index) | [x] |
| T6 | Hardening: error envelope, logging, OpenAPI, seed data | S | – | [x] |
| T7 | README and demo script | S | – | [x] |

**Total: 1 L + 4 M + 2 S.** Roughly a day of focused work. The size sits almost entirely in T5, which is correct — it is the graded feature and the only one `requirements.md` demands unit tests for.

### Prerequisites

Nothing is installed on this machine yet. Before T1: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), and Docker Desktop with Compose. T1's first acceptance criterion is that all three respond to a version check.

### Definition of done, every task

From `microservice-implement`. Run these before ticking a task, not after.

```
- [ ] Acceptance criteria all verified by hand or by test
- [ ] Tests for this task written and passing
- [ ] ruff check + ruff format --check clean
- [ ] mypy app clean
- [ ] Migration applies and reverts, if the task has one
- [ ] Service still starts and /health responds
- [ ] docs/design.md amended if implementation changed a decision
```

---

### T1 — Skeleton, configuration and health check

- [ ] **Delivers:** a FastAPI app that starts, reads configuration from the environment, and reports database reachability. Postgres running in Docker. Lint, type-check and test commands all wired and passing on an empty suite.
- [ ] **Touches:** `pyproject.toml`, `docker-compose.yml`, `.env.example`, `.gitignore`, `app/__init__.py`, `app/config.py`, `app/db.py`, `app/main.py`, `tests/conftest.py`
- [ ] **Migration:** none
- [ ] **Design reference:** §5, and the stack table in `microservice-workflow`
- [ ] **Acceptance criteria:**
  - `python --version` reports 3.12+, `uv --version` and `docker compose version` both succeed.
  - `git init` has been run and `.gitignore` excludes `.env`, `.venv`, `__pycache__`.
  - `uv sync` installs the dependency set from `reference.md`, including `pytest-asyncio>=0.26`.
  - `docker compose up -d db` reaches a healthy Postgres, and a second `products_test` database exists for the suite.
  - `uv run uvicorn app.main:app` starts and `GET /health` returns `200` with `{"status": "ok"}` including a successful `SELECT 1` against the database.
  - `GET /health` returns `503` with the standard error body when the database is unreachable — verified by stopping the container.
  - Missing `DATABASE_URL` fails at startup with a clear message, not a `500` on first request.
  - `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app` and `uv run pytest` all exit zero.
- [ ] **Demo:** `docker compose up -d db && uv run uvicorn app.main:app & curl localhost:8000/health`

### T2 — Models, Alembic and the first migration

- [ ] **Delivers:** `Category` and `Product` ORM models matching the design schema exactly, Alembic configured for async, and one migration creating both tables with every constraint and btree index.
- [ ] **Touches:** `app/models/base.py`, `app/models/category.py`, `app/models/product.py`, `app/models/__init__.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial.py`, `tests/integration/test_migrations.py`
- [ ] **Migration:** yes — initial schema
- [ ] **Design reference:** §2, §3, D1, D4, D5, D6, D7
- [ ] **Acceptance criteria:**
  - Models use SQLAlchemy 2.0 style throughout: `DeclarativeBase`, `Mapped[...]`, `mapped_column()`.
  - Every relationship is declared `lazy="raise"`, so an accidental lazy load fails loudly instead of raising `MissingGreenlet` later.
  - `price` is `Numeric(12, 2)` and maps to `Decimal` in Python. No `float` appears anywhere near it.
  - `uv run alembic upgrade head` creates both tables; `alembic downgrade base` drops them cleanly.
  - The migration includes, and `\d products` in `psql` confirms: `uq_products_sku`, `ck_products_price_non_negative`, `ix_products_category_id`, `ix_products_price`, `ix_products_created_at_id`, both FKs with `ON DELETE RESTRICT`.
  - The migration includes, and `\d categories` confirms: `ck_categories_no_self_parent`, `uq_categories_parent_name`, `ix_categories_parent_id`.
  - Inserting two products with the same SKU raises a database integrity error, not a duplicate row.
  - `INSERT` with a negative price is rejected by the `CHECK`, proving the constraint is real and not only in Pydantic.
  - Deleting a category that has products fails at the database level with a foreign key violation.
  - `tests/integration/test_migrations.py` runs `alembic upgrade head` then `downgrade base` against a scratch database and passes. A suite built from `metadata.create_all` proves nothing about Alembic.
- [ ] **Demo:** `uv run alembic upgrade head && docker compose exec db psql -U products -d products -c '\d products'`

### T3 — Category CRUD

- [ ] **Delivers:** the five category endpoints, sibling-name uniqueness, cycle prevention on re-parent, and `RESTRICT` delete surfaced as a useful `409`.
- [ ] **Touches:** `app/schemas/category.py`, `app/repositories/category.py`, `app/services/category.py`, `app/api/v1/categories.py`, `app/errors.py`, `tests/integration/test_categories.py`
- [ ] **Migration:** none
- [ ] **Design reference:** §4.1, §4.4, D2, D3
- [ ] **Acceptance criteria:**
  - `POST /api/v1/categories` with `{"name": "Electronics"}` returns `201` and a category with `parent_id: null`.
  - `POST` with a `parent_id` that does not exist returns `422 validation_error`, not a `500` from the foreign key.
  - `POST` with a name already used by a sibling returns `409 duplicate_category_name`.
  - `GET /api/v1/categories?parent_id=1` returns only direct children, in the standard page envelope.
  - `GET /api/v1/categories/{id}` returns `404 not_found` for an unknown id.
  - `PATCH` with `{"parent_id": <own id>}` returns `409 category_cycle`.
  - `PATCH` making a category a child of its own descendant returns `409 category_cycle` — the case the database `CHECK` cannot catch, so it must be covered by a test at depth 3.
  - `PATCH` with `{"name": "..."}` alone leaves `parent_id` untouched.
  - `DELETE` on a category with child categories returns `409 category_not_empty`, and the message names children as the blocker.
  - `DELETE` on a category holding products returns `409 category_not_empty` naming products as the blocker.
  - `DELETE` on an empty leaf returns `204`, and a subsequent `GET` returns `404`.
  - Names are trimmed on write: `"  Phones  "` is stored as `"Phones"`.
- [ ] **Demo:** `curl -X POST localhost:8000/api/v1/categories -H 'content-type: application/json' -d '{"name":"Electronics"}'`

### T4 — Product CRUD

- [ ] **Delivers:** create, read by id, read by SKU, partial update, delete. Search is deliberately excluded — that is T5.
- [ ] **Touches:** `app/schemas/product.py`, `app/repositories/product.py`, `app/api/v1/products.py`, `tests/integration/test_products.py`
- [ ] **Migration:** none
- [ ] **Design reference:** §4.2, §4.4, D4, D5, D6, D12, D14
- [ ] **Acceptance criteria:**
  - `POST /api/v1/products` with a valid body returns `201` and the created product, with `price` serialized as a JSON string.
  - A lowercase `sku` on create is stored and returned uppercase.
  - A duplicate SKU returns `409 duplicate_sku`, and the message names the SKU.
  - A SKU differing only in case from an existing one also returns `409` — this is the whole point of normalizing on write.
  - A SKU violating the format pattern returns `422 validation_error`.
  - A `category_id` that does not exist returns `422`, not a `500`.
  - A negative price returns `422`; a price of `0` is accepted.
  - A price with three decimal places returns `422` rather than being silently rounded.
  - `image_url` may be omitted or `null`; a non-`http`/`https` value returns `422`.
  - An omitted `description` is stored as `""` and returned as `""`, never `null`.
  - `GET /api/v1/products/{id}` returns the product; an unknown id returns `404 not_found`.
  - `GET /api/v1/products/by-sku/smart-1` finds `SMART-1`, proving the route is case-insensitive on input.
  - `PATCH` with only `{"price": "..."}` changes the price and leaves every other field untouched.
  - `PATCH` attempting to change `sku` returns `422` with a message explaining SKUs are immutable.
  - `PATCH` bumps `updated_at` and leaves `created_at` unchanged.
  - `DELETE` returns `204`; a second `DELETE` on the same id returns `404`.
- [ ] **Demo:** `curl -X POST localhost:8000/api/v1/products -H 'content-type: application/json' -d @examples/product.json && curl localhost:8000/api/v1/products/by-sku/SMART-1`

### T5 — Search

The graded task. Criteria are split per filter so the test matrix in `microservice-test` maps onto them one to one.

- [ ] **Delivers:** `GET /api/v1/products` with all nine parameters, the recursive subtree CTE, stable sorting, limit/offset pagination with an accurate total, and the trigram index that makes text search indexable.
- [ ] **Touches:** `app/repositories/product_search.py`, `app/schemas/product.py`, `app/api/v1/products.py`, `alembic/versions/0002_trigram_index.py`, `tests/unit/test_search_query.py`, `tests/integration/test_search.py`, `tests/factories.py`, `tests/conftest.py`
- [ ] **Migration:** yes — `pg_trgm` extension and `ix_products_title_trgm`, written by hand because autogenerate will not produce it
- [ ] **Design reference:** §4.3, §5, D8, D9, D10, D11
- [ ] **Structural criteria** — these are what make the rest testable:
  - `build_search_query(ProductFilters) -> Select` is a pure function: no session, no I/O, no awaits.
  - `build_count_query` shares the same `_apply_filters` helper, so `total` and `items` cannot disagree about what matched.
  - `ProductSearchParams` is a Pydantic model bound with `Annotated[..., Query()]` and set to `extra="forbid"`.
- [ ] **Acceptance criteria — text `q`:**
  - `?q=phone` matches products whose title contains "phone" and products whose description contains it.
  - Matching is case-insensitive and mid-word: `?q=PHONE` and `?q=hon` both match "Smart Phone X".
  - A term with no matches returns `200` with `items: []` and `total: 0`, not `404`.
  - `?q=50%` treats `%` literally and does not match everything. Same for `_`.
- [ ] **Acceptance criteria — `sku`:**
  - `?sku=SMART-1` returns exactly that product; `?sku=smart-1` returns it too.
  - An unknown SKU returns an empty page.
  - `?q=` and `?sku=` supplied together AND rather than OR.
- [ ] **Acceptance criteria — category:**
  - `?category_id=<electronics>` returns products in Electronics and in every category beneath it, at any depth — verified on a tree at least three levels deep.
  - `?category_id=<phones>&include_descendants=false` returns only products directly in Phones.
  - `?category_id=<leaf>` works where the category has no children.
  - An unknown `category_id` returns an empty page, not `404` (D9).
- [ ] **Acceptance criteria — price range:**
  - `?price_min=` alone, `?price_max=` alone, and both together each filter correctly.
  - Bounds are inclusive: a product priced exactly `500.00` is returned by `?price_max=500`.
  - `?price_min=100&price_max=50` returns `422`, not an empty page.
- [ ] **Acceptance criteria — combinations:**
  - `?q=phone&category_id=<electronics>&price_max=500` returns only products satisfying all three.
  - A combination matching nothing returns an empty page with `total: 0`.
  - A fixture product deliberately matches `q` but sits outside the category branch, so an OR bug fails the test.
- [ ] **Acceptance criteria — sorting and pagination:**
  - Each of the six `sort` values orders correctly.
  - Every sort appends an `id ASC` tiebreaker, so products with equal prices keep a stable order.
  - Two adjacent pages of a sort over equal values are disjoint and together cover every match — the test that catches a missing tiebreaker.
  - `total` is the count of all matches, not the page size.
  - An `offset` past the end returns an empty `items` with the true `total`.
  - Defaults with no parameters are `limit=20`, `offset=0`, `sort=-created_at`.
- [ ] **Acceptance criteria — validation:**
  - `?limit=0`, `?limit=101`, `?offset=-1`, `?price_min=-1`, `?sort=secret_field` each return `422`.
  - `?categoryid=1` — a typo in a parameter name — returns `422` rather than being ignored.
- [ ] **Acceptance criteria — performance and hygiene:**
  - `EXPLAIN` on `?q=phone` shows the trigram index used for the title leg.
  - The endpoint issues exactly two queries per request, one for items and one for the count. No N+1 from serializing categories.
  - Unit tests in `tests/unit` pass with no database running at all.
- [ ] **Demo:** `curl 'localhost:8000/api/v1/products?q=phone&category_id=1&price_min=100&price_max=500&sort=price'`

### T6 — Hardening

- [ ] **Delivers:** the single error envelope applied everywhere including FastAPI's own validation errors, structured request logging, an OpenAPI document worth reading, and seed data so the demo has something in it.
- [ ] **Touches:** `app/errors.py`, `app/main.py`, `app/logging.py`, `scripts/seed.py`, `app/api/v1/*.py` (docstrings and response examples)
- [ ] **Migration:** none
- [ ] **Design reference:** §4.4, D13
- [ ] **Acceptance criteria:**
  - Every error response in the suite matches `{"error": {"code", "message", "details"}}` — including `422`s, via a `RequestValidationError` handler. A test asserts the shape across one of each status code.
  - `details` on a validation error names the offending field and why.
  - An unhandled exception returns `500` with the same envelope and a generic message, never a stack trace or a database error string.
  - Each request logs one structured line with method, path, status and duration.
  - `/docs` shows a description and at least one example per endpoint, and the search parameters carry their semantics from §4.3 rather than bare types.
  - `uv run python -m scripts.seed` creates the three-level category tree and a handful of products, and is idempotent.
- [ ] **Demo:** `uv run python -m scripts.seed && open localhost:8000/docs`

### T7 — README and demo

- [ ] **Delivers:** documentation that gets a reviewer from a clean clone to a running service with data in under five minutes.
- [ ] **Touches:** `README.md`
- [ ] **Migration:** none
- [ ] **Design reference:** the whole document, linked rather than repeated
- [ ] **Acceptance criteria:**
  - Setup, run, migrate, seed and test commands, each copy-pasteable and each actually executed once from a clean state to confirm.
  - `docker compose down -v && docker compose up -d db && uv run alembic upgrade head && uv run python -m scripts.seed && uv run pytest` succeeds end to end.
  - A short "design decisions" section linking to `docs/design.md` instead of duplicating it.
  - The example search calls from §4.3, verified against the seed data so they return non-empty results.
  - A note on what is deliberately out of scope, pointing at the non-goals table.
- [ ] **Demo:** follow the README verbatim on a clean clone.

---

## Scope guard

If time runs short, cut from the bottom. T1–T5 is a complete, defensible answer to `requirements.md`; T6 and T7 make it presentable. Do not cut into T5 — trimming the search test matrix removes the one thing the assignment explicitly asks for.
