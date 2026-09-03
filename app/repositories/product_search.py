from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, func, or_, select

from app.models import Category, Product

SORTABLE = {
    "price": Product.price,
    "title": Product.title,
    "created_at": Product.created_at,
}


@dataclass(frozen=True, slots=True)
class ProductFilters:
    q: str | None = None
    sku: str | None = None
    category_id: int | None = None
    include_descendants: bool = True
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    sort: str = "-created_at"
    limit: int = 20
    offset: int = 0


def _escape_like(value: str) -> str:
    """A literal % or _ from the client must not act as a wildcard."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _descendant_ids(root_id: int) -> Select[tuple[int]]:
    """Recursive CTE returning the root category and every category beneath it."""
    cat = Category.__table__
    subtree = select(cat.c.id).where(cat.c.id == root_id).cte("subtree", recursive=True)
    subtree = subtree.union_all(select(cat.c.id).join(subtree, cat.c.parent_id == subtree.c.id))
    return select(subtree.c.id)


def _apply_filters(stmt: Select[Any], f: ProductFilters) -> Select[Any]:
    if f.q:
        term = f"%{_escape_like(f.q)}%"
        stmt = stmt.where(
            or_(
                Product.title.ilike(term, escape="\\"),
                Product.description.ilike(term, escape="\\"),
            )
        )
    if f.sku:
        stmt = stmt.where(Product.sku == f.sku.upper())
    if f.category_id is not None:
        stmt = stmt.where(
            Product.category_id.in_(_descendant_ids(f.category_id))
            if f.include_descendants
            else Product.category_id == f.category_id
        )
    if f.price_min is not None:
        stmt = stmt.where(Product.price >= f.price_min)
    if f.price_max is not None:
        stmt = stmt.where(Product.price <= f.price_max)
    return stmt


def _order_by(sort: str) -> list[ColumnElement[Any]]:
    column = SORTABLE[sort.lstrip("-")]
    primary = column.desc() if sort.startswith("-") else column.asc()
    return [primary, Product.id.asc()]


def build_search_query(f: ProductFilters) -> Select[tuple[Product]]:
    stmt = _apply_filters(select(Product), f)
    return cast(
        Select[tuple[Product]],
        stmt.order_by(*_order_by(f.sort)).limit(f.limit).offset(f.offset),
    )


def build_count_query(f: ProductFilters) -> Select[tuple[int]]:
    return cast(Select[tuple[int]], _apply_filters(select(func.count(Product.id)), f))
