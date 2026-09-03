import os
import subprocess
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Category, Product


@pytest.mark.slow
def test_migrations_apply_and_revert() -> None:
    settings = get_settings()
    env = {**os.environ, "DATABASE_URL": settings.migrate_database_url}
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env=env, check=True)
    subprocess.run(["uv", "run", "alembic", "downgrade", "base"], env=env, check=True)
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env=env, check=True)


async def test_duplicate_sku_rejected_at_database(session: AsyncSession) -> None:
    category = Category(name="Root")
    session.add(category)
    await session.flush()
    session.add(
        Product(
            sku="ABC-1", title="One", description="", price=Decimal("1.00"), category_id=category.id
        )
    )
    await session.flush()
    session.add(
        Product(
            sku="ABC-1", title="Two", description="", price=Decimal("2.00"), category_id=category.id
        )
    )
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.flush()


async def test_negative_price_rejected_at_database(session: AsyncSession) -> None:
    category = Category(name="Priced")
    session.add(category)
    await session.flush()
    session.add(
        Product(
            sku="NEG-1",
            title="Negative",
            description="",
            price=Decimal("-0.01"),
            category_id=category.id,
        )
    )
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.flush()


async def test_category_delete_restricted_by_products(session: AsyncSession) -> None:
    category = Category(name="Held")
    session.add(category)
    await session.flush()
    session.add(
        Product(
            sku="HOLD-1",
            title="Held",
            description="",
            price=Decimal("1.00"),
            category_id=category.id,
        )
    )
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.delete(category)
            await session.flush()


async def test_expected_indexes_exist(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename IN ('products', 'categories')
                """
            )
        )
    ).all()
    names = {row[0] for row in rows}
    assert "uq_products_sku" in names
    assert "ix_products_category_id" in names
    assert "ix_products_price" in names
    assert "ix_products_created_at_id" in names
    assert "ix_categories_parent_id" in names
