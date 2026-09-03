from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, NotFound, Unprocessable
from app.models import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = CategoryRepository(session)
        self._session = session

    async def get(self, category_id: int) -> Category:
        category = await self._repo.get(category_id)
        if category is None:
            raise NotFound(f"Category {category_id} was not found")
        return category

    async def list(
        self, *, parent_id: int | None, limit: int, offset: int, filter_parent: bool
    ) -> tuple[Sequence[Category], int]:
        return await self._repo.list(
            parent_id=parent_id, limit=limit, offset=offset, filter_parent=filter_parent
        )

    async def create(self, payload: CategoryCreate) -> Category:
        if payload.parent_id is not None and not await self._repo.exists(payload.parent_id):
            raise Unprocessable(
                f"Parent category {payload.parent_id} was not found",
                details=[{"field": "parent_id", "message": "unknown parent category"}],
            )
        await self._assert_unique_sibling_name(payload.name, payload.parent_id)
        category = Category(name=payload.name, parent_id=payload.parent_id)
        try:
            async with self._session.begin_nested():
                return await self._repo.add(category)
        except IntegrityError as exc:
            raise Conflict(
                f"A category named '{payload.name}' already exists under the same parent",
                code="duplicate_category_name",
            ) from exc

    async def update(self, category_id: int, payload: CategoryUpdate) -> Category:
        category = await self.get(category_id)
        new_name = category.name
        if "name" in payload.model_fields_set and payload.name is not None:
            new_name = payload.name
        new_parent_id = (
            payload.parent_id if "parent_id" in payload.model_fields_set else category.parent_id
        )

        if new_parent_id is not None:
            if not await self._repo.exists(new_parent_id):
                raise Unprocessable(
                    f"Parent category {new_parent_id} was not found",
                    details=[{"field": "parent_id", "message": "unknown parent category"}],
                )
            if await self._would_cycle(category_id, new_parent_id):
                raise Conflict(
                    "Re-parenting this category would create a cycle",
                    code="category_cycle",
                )

        if new_name != category.name or new_parent_id != category.parent_id:
            await self._assert_unique_sibling_name(new_name, new_parent_id, exclude_id=category.id)

        category.name = new_name
        category.parent_id = new_parent_id
        try:
            async with self._session.begin_nested():
                await self._session.flush()
                await self._session.refresh(category)
        except IntegrityError as exc:
            raise Conflict(
                f"A category named '{new_name}' already exists under the same parent",
                code="duplicate_category_name",
            ) from exc
        return category

    async def delete(self, category_id: int) -> None:
        category = await self.get(category_id)
        child_count = await self._repo.count_children(category_id)
        product_count = await self._repo.count_products(category_id)
        if child_count or product_count:
            blockers = []
            if child_count:
                blockers.append(f"{child_count} child categor{'y' if child_count == 1 else 'ies'}")
            if product_count:
                blockers.append(f"{product_count} product{'s' if product_count != 1 else ''}")
            raise Conflict(
                f"Category {category_id} cannot be deleted while it has {' and '.join(blockers)}",
                code="category_not_empty",
            )
        await self._repo.delete(category)

    async def _assert_unique_sibling_name(
        self, name: str, parent_id: int | None, *, exclude_id: int | None = None
    ) -> None:
        existing = await self._repo.find_sibling_by_name(name, parent_id)
        if existing is not None and existing.id != exclude_id:
            raise Conflict(
                f"A category named '{name}' already exists under the same parent",
                code="duplicate_category_name",
            )

    async def _would_cycle(self, category_id: int, new_parent_id: int) -> bool:
        if new_parent_id == category_id:
            return True
        current_id: int | None = new_parent_id
        seen: set[int] = set()
        while current_id is not None:
            if current_id == category_id:
                return True
            if current_id in seen:
                return True
            seen.add(current_id)
            current = await self._repo.get(current_id)
            current_id = None if current is None else current.parent_id
        return False
