from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models.base import Base
from tests.factories import make_category, make_product

settings = get_settings()


@pytest_asyncio.fixture(scope="session")
async def engine():
    test_engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_products_title_trgm "
                "ON products USING gin (title gin_trgm_ops)"
            )
        )
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """One transaction per test, discarded afterwards.

    join_transaction_mode="create_savepoint" means a commit() inside application
    code opens a savepoint within this outer transaction instead of ending it.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    db = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield db
    finally:
        await db.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def catalog(session: AsyncSession) -> dict:
    """electronics > phones > smartphones, plus a sibling branch."""
    electronics = await make_category(session, "Electronics")
    phones = await make_category(session, "Phones", parent=electronics)
    smartphones = await make_category(session, "Smartphones", parent=phones)
    books = await make_category(session, "Books")

    await make_product(session, "PHONE-1", phones, title="Basic Phone", price="80.00")
    await make_product(session, "SMART-1", smartphones, title="Smart Phone X", price="799.00")
    await make_product(session, "SMART-2", smartphones, title="Smart Phone Mini", price="499.00")
    await make_product(
        session,
        "BOOK-1",
        books,
        title="Phone Repair Manual",
        description="Fix a phone",
        price="25.00",
    )
    return {
        "electronics": electronics,
        "phones": phones,
        "smartphones": smartphones,
        "books": books,
    }
