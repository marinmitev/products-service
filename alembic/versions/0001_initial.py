"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_categories_no_self_parent",
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("parent_id", "name", name="uq_categories_parent_name"),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_price", "products", ["price"])
    op.create_index("ix_products_created_at_id", "products", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_products_created_at_id", table_name="products")
    op.drop_index("ix_products_price", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")
