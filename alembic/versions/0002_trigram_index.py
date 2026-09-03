"""trigram index for product title search

Revision ID: 0002_trigram
Revises: 0001_initial
Create Date: 2026-09-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_trigram"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_products_title_trgm ON products USING gin (title gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_title_trgm")
