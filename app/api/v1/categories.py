from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.common import Page
from app.services.category import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


def _service(session: Annotated[AsyncSession, Depends(get_session)]) -> CategoryService:
    return CategoryService(session)


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
)
async def create_category(
    payload: CategoryCreate,
    service: Annotated[CategoryService, Depends(_service)],
) -> CategoryRead:
    return CategoryRead.model_validate(await service.create(payload))


@router.get(
    "",
    response_model=Page[CategoryRead],
    summary="List categories",
)
async def list_categories(
    service: Annotated[CategoryService, Depends(_service)],
    parent_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    filter_parent: Annotated[
        bool,
        Query(
            description=(
                "When true, filters categories by parent relationship. "
                "If `parent_id` is omitted it returns only root categories; "
                "if `parent_id` is provided it returns that parent's direct children."
            )
        ),
    ] = False,
) -> Page[CategoryRead]:
    """List categories. Pass `parent_id` to restrict to that parent's children.

    `filter_parent=true` without `parent_id` returns only roots.
    """
    should_filter = filter_parent or parent_id is not None
    items, total = await service.list(
        parent_id=parent_id, limit=limit, offset=offset, filter_parent=should_filter
    )
    return Page(
        items=[CategoryRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Get a category",
)
async def get_category(
    category_id: int,
    service: Annotated[CategoryService, Depends(_service)],
) -> CategoryRead:
    return CategoryRead.model_validate(await service.get(category_id))


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Update a category",
)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    service: Annotated[CategoryService, Depends(_service)],
) -> CategoryRead:
    return CategoryRead.model_validate(await service.update(category_id, payload))


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category",
)
async def delete_category(
    category_id: int,
    service: Annotated[CategoryService, Depends(_service)],
) -> Response:
    await service.delete(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
