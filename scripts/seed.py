"""Idempotent demo catalogue: Electronics > Phones > Smartphones, plus Books."""

import asyncio

from app.db import SessionFactory
from app.models import Category, Product
from app.repositories.product import ProductRepository
from app.schemas.category import CategoryCreate
from app.schemas.product import ProductCreate
from app.services.category import CategoryService
from app.services.product import ProductService


async def _get_or_create_category(
    service: CategoryService, name: str, parent_id: int | None = None
) -> Category:
    items, _ = await service.list(parent_id=parent_id, limit=100, offset=0, filter_parent=True)
    for item in items:
        if item.name == name:
            return item
    return await service.create(CategoryCreate(name=name, parent_id=parent_id))


async def _get_or_create_product(
    service: ProductService, repo: ProductRepository, payload: ProductCreate
) -> Product:
    existing = await repo.get_by_sku(payload.sku)
    if existing is not None:
        return existing
    return await service.create(payload)


async def seed() -> None:
    async with SessionFactory() as session:
        categories = CategoryService(session)
        products = ProductService(session)
        product_repo = ProductRepository(session)

        electronics = await _get_or_create_category(categories, "Electronics")
        phones = await _get_or_create_category(categories, "Phones", electronics.id)
        smartphones = await _get_or_create_category(categories, "Smartphones", phones.id)
        books = await _get_or_create_category(categories, "Books")

        await _get_or_create_product(
            products,
            product_repo,
            ProductCreate(
                sku="PHONE-1",
                title="Basic Phone",
                description="A simple phone",
                price="80.00",
                category_id=phones.id,
                image_url="https://cdn.example.com/phone-1.jpg",
            ),
        )
        await _get_or_create_product(
            products,
            product_repo,
            ProductCreate(
                sku="SMART-1",
                title="Smart Phone X",
                description="Flagship smartphone",
                price="799.00",
                category_id=smartphones.id,
                image_url="https://cdn.example.com/smart-1.jpg",
            ),
        )
        await _get_or_create_product(
            products,
            product_repo,
            ProductCreate(
                sku="SMART-2",
                title="Smart Phone Mini",
                description="Compact smartphone",
                price="499.00",
                category_id=smartphones.id,
                image_url="https://cdn.example.com/smart-2.jpg",
            ),
        )
        await _get_or_create_product(
            products,
            product_repo,
            ProductCreate(
                sku="BOOK-1",
                title="Phone Repair Manual",
                description="Fix a phone at home",
                price="25.00",
                category_id=books.id,
            ),
        )
        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
