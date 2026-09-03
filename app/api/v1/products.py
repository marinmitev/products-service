from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories.product_search import ProductFilters
from app.schemas.common import Page
from app.schemas.product import ProductCreate, ProductRead, ProductSearchParams, ProductUpdate
from app.services.product import ProductService

router = APIRouter(prefix="/products", tags=["products"])


def _service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProductService:
    return ProductService(session)


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
async def create_product(
    payload: ProductCreate,
    service: Annotated[ProductService, Depends(_service)],
) -> ProductRead:
    return ProductRead.model_validate(await service.create(payload))


@router.get(
    "",
    response_model=Page[ProductRead],
    summary="List and search products",
    description=(
        "Filter the catalogue. All parameters are optional and combine with AND. "
        "`q` is a case-insensitive substring match against title or description. "
        "`category_id` includes descendants by default."
    ),
)
async def search_products(
    params: Annotated[ProductSearchParams, Query()],
    service: Annotated[ProductService, Depends(_service)],
) -> Page[ProductRead]:
    filters = ProductFilters(**params.model_dump())
    items, total = await service.search(filters)
    return Page(
        items=[ProductRead.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get(
    "/by-sku/{sku}",
    response_model=ProductRead,
    summary="Get a product by SKU",
)
async def get_product_by_sku(
    sku: str,
    service: Annotated[ProductService, Depends(_service)],
) -> ProductRead:
    return ProductRead.model_validate(await service.get_by_sku(sku))


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Get a product",
)
async def get_product(
    product_id: int,
    service: Annotated[ProductService, Depends(_service)],
) -> ProductRead:
    return ProductRead.model_validate(await service.get(product_id))


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    summary="Update a product",
)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    service: Annotated[ProductService, Depends(_service)],
) -> ProductRead:
    return ProductRead.model_validate(await service.update(product_id, payload))


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product",
)
async def delete_product(
    product_id: int,
    service: Annotated[ProductService, Depends(_service)],
) -> Response:
    await service.delete(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
