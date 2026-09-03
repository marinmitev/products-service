from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, NotFound, Unprocessable
from app.models import Product
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.repositories.product_search import ProductFilters
from app.schemas.product import ProductCreate, ProductUpdate


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self._products = ProductRepository(session)
        self._categories = CategoryRepository(session)
        self._session = session

    async def get(self, product_id: int) -> Product:
        product = await self._products.get(product_id)
        if product is None:
            raise NotFound(f"Product {product_id} was not found")
        return product

    async def get_by_sku(self, sku: str) -> Product:
        product = await self._products.get_by_sku(sku)
        if product is None:
            raise NotFound(f"Product with SKU '{sku.upper()}' was not found")
        return product

    async def create(self, payload: ProductCreate) -> Product:
        await self._require_category(payload.category_id)
        if await self._products.get_by_sku(payload.sku) is not None:
            raise Conflict(
                f"A product with SKU '{payload.sku}' already exists.",
                code="duplicate_sku",
            )
        product = Product(
            sku=payload.sku,
            title=payload.title,
            description=payload.description,
            image_url=payload.image_url,
            price=payload.price,
            category_id=payload.category_id,
        )
        try:
            async with self._session.begin_nested():
                return await self._products.add(product)
        except IntegrityError as exc:
            raise Conflict(
                f"A product with SKU '{payload.sku}' already exists.",
                code="duplicate_sku",
            ) from exc

    async def update(self, product_id: int, payload: ProductUpdate) -> Product:
        product = await self.get(product_id)
        if "category_id" in payload.model_fields_set and payload.category_id is not None:
            await self._require_category(payload.category_id)
            product.category_id = payload.category_id
        if "title" in payload.model_fields_set and payload.title is not None:
            product.title = payload.title
        if "description" in payload.model_fields_set and payload.description is not None:
            product.description = payload.description
        if "image_url" in payload.model_fields_set:
            product.image_url = payload.image_url
        if "price" in payload.model_fields_set and payload.price is not None:
            product.price = payload.price
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def delete(self, product_id: int) -> None:
        product = await self.get(product_id)
        await self._products.delete(product)

    async def search(self, filters: ProductFilters) -> tuple[Sequence[Product], int]:
        return await self._products.search(filters)

    async def _require_category(self, category_id: int) -> None:
        if not await self._categories.exists(category_id):
            raise Unprocessable(
                f"Category {category_id} was not found",
                details=[{"field": "category_id", "message": "unknown category"}],
            )


def filters_from_params(
    *,
    q: str | None,
    sku: str | None,
    category_id: int | None,
    include_descendants: bool,
    price_min: Decimal | None,
    price_max: Decimal | None,
    sort: str,
    limit: int,
    offset: int,
) -> ProductFilters:
    return ProductFilters(
        q=q,
        sku=sku,
        category_id=category_id,
        include_descendants=include_descendants,
        price_min=price_min,
        price_max=price_max,
        sort=sort,
        limit=limit,
        offset=offset,
    )
