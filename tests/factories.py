from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Product


async def make_category(
    session: AsyncSession, name: str, parent: Category | None = None
) -> Category:
    category = Category(name=name, parent_id=parent.id if parent else None)
    session.add(category)
    await session.flush()
    return category


async def make_product(
    session: AsyncSession,
    sku: str,
    category: Category,
    *,
    title: str | None = None,
    description: str = "",
    price: str = "9.99",
    image_url: str | None = None,
) -> Product:
    product = Product(
        sku=sku.upper(),
        title=title or sku.replace("-", " ").title(),
        description=description,
        price=Decimal(price),
        category_id=category.id,
        image_url=image_url,
    )
    session.add(product)
    await session.flush()
    return product
