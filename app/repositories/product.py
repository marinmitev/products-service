from collections.abc import Sequence
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product
from app.repositories.product_search import ProductFilters, build_count_query, build_search_query


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, product_id: int) -> Product | None:
        return await self._session.get(Product, product_id)

    async def get_by_sku(self, sku: str) -> Product | None:
        stmt = select(Product).where(Product.sku == sku.upper())
        return cast(Product | None, await self._session.scalar(stmt))

    async def add(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        await self._session.delete(product)
        await self._session.flush()

    async def search(self, filters: ProductFilters) -> tuple[Sequence[Product], int]:
        items = (await self._session.scalars(build_search_query(filters))).all()
        total = await self._session.scalar(build_count_query(filters)) or 0
        return items, total
