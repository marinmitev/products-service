from collections.abc import Sequence
from typing import cast

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Product


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, category_id: int) -> Category | None:
        return await self._session.get(Category, category_id)

    async def exists(self, category_id: int) -> bool:
        return await self.get(category_id) is not None

    async def find_sibling_by_name(self, name: str, parent_id: int | None) -> Category | None:
        stmt = select(Category).where(Category.name == name)
        if parent_id is None:
            stmt = stmt.where(Category.parent_id.is_(None))
        else:
            stmt = stmt.where(Category.parent_id == parent_id)
        return cast(Category | None, await self._session.scalar(stmt))

    async def list(
        self, *, parent_id: int | None, limit: int, offset: int, filter_parent: bool
    ) -> tuple[Sequence[Category], int]:
        filters: list[ColumnElement[bool]] = []
        if filter_parent:
            if parent_id is None:
                filters.append(Category.parent_id.is_(None))
            else:
                filters.append(Category.parent_id == parent_id)
        items_stmt = (
            select(Category)
            .where(*filters)
            .order_by(Category.name.asc(), Category.id.asc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count(Category.id)).where(*filters)
        items = (await self._session.scalars(items_stmt)).all()
        total = await self._session.scalar(count_stmt) or 0
        return items, total

    async def add(self, category: Category) -> Category:
        self._session.add(category)
        await self._session.flush()
        await self._session.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        await self._session.delete(category)
        await self._session.flush()

    async def count_children(self, category_id: int) -> int:
        stmt = select(func.count(Category.id)).where(Category.parent_id == category_id)
        return await self._session.scalar(stmt) or 0

    async def count_products(self, category_id: int) -> int:
        stmt = select(func.count(Product.id)).where(Product.category_id == category_id)
        return await self._session.scalar(stmt) or 0
