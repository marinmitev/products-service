from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_product


def skus(payload: dict) -> set[str]:
    return {item["sku"] for item in payload["items"]}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("q=phone", {"PHONE-1", "SMART-1", "SMART-2", "BOOK-1"}),
        ("q=PHONE", {"PHONE-1", "SMART-1", "SMART-2", "BOOK-1"}),
        ("q=mini", {"SMART-2"}),
        ("q=nothing-here", set()),
        ("sku=SMART-1", {"SMART-1"}),
        ("sku=smart-1", {"SMART-1"}),
        ("sku=NOPE-1", set()),
        ("price_min=500", {"SMART-1"}),
        ("price_max=100", {"PHONE-1", "BOOK-1"}),
        ("price_min=25&price_max=80", {"PHONE-1", "BOOK-1"}),
    ],
)
async def test_single_filters(
    client: AsyncClient, catalog: dict, query: str, expected: set[str]
) -> None:
    response = await client.get(f"/api/v1/products?{query}")
    assert response.status_code == 200
    assert skus(response.json()) == expected


async def test_q_matches_description(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?q=Fix")
    assert skus(response.json()) == {"BOOK-1"}


async def test_q_mid_word(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?q=hon")
    assert "SMART-1" in skus(response.json())


async def test_literal_percent_is_not_a_wildcard(
    client: AsyncClient, session: AsyncSession, catalog: dict
) -> None:
    await make_product(session, "PCT-1", catalog["books"], title="50% off case")
    wild = await client.get("/api/v1/products?q=%")
    assert wild.status_code == 200
    assert skus(wild.json()) == {"PCT-1"}


async def test_q_and_sku_combine_with_and(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?q=phone&sku=BOOK-1")
    assert skus(response.json()) == {"BOOK-1"}


async def test_category_filter_includes_descendants(client: AsyncClient, catalog: dict) -> None:
    response = await client.get(f"/api/v1/products?category_id={catalog['electronics'].id}")
    assert skus(response.json()) == {"PHONE-1", "SMART-1", "SMART-2"}


async def test_category_filter_can_exclude_descendants(client: AsyncClient, catalog: dict) -> None:
    response = await client.get(
        f"/api/v1/products?category_id={catalog['phones'].id}&include_descendants=false"
    )
    assert skus(response.json()) == {"PHONE-1"}


async def test_leaf_category_filter(client: AsyncClient, catalog: dict) -> None:
    response = await client.get(f"/api/v1/products?category_id={catalog['smartphones'].id}")
    assert skus(response.json()) == {"SMART-1", "SMART-2"}


async def test_unknown_category_filter_is_empty_page(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?category_id=99999")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


async def test_price_bounds_inclusive(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?price_max=499.00")
    assert "SMART-2" in skus(response.json())
    assert "SMART-1" not in skus(response.json())


async def test_filters_combine_with_and(client: AsyncClient, catalog: dict) -> None:
    response = await client.get(
        f"/api/v1/products?q=phone&category_id={catalog['electronics'].id}&price_max=500"
    )
    assert skus(response.json()) == {"PHONE-1", "SMART-2"}


async def test_combination_matching_nothing(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?q=phone&sku=NOPE-9")
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


async def test_sort_price_ascending(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?sort=price")
    prices = [Decimal(item["price"]) for item in response.json()["items"]]
    assert prices == sorted(prices)


async def test_sort_price_descending(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?sort=-price")
    prices = [Decimal(item["price"]) for item in response.json()["items"]]
    assert prices == sorted(prices, reverse=True)


async def test_total_counts_all_matches_not_just_the_page(
    client: AsyncClient, catalog: dict
) -> None:
    response = await client.get("/api/v1/products?q=phone&limit=2")
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 4


async def test_pages_do_not_overlap(client: AsyncClient, catalog: dict) -> None:
    first = await client.get("/api/v1/products?sort=price&limit=2&offset=0")
    second = await client.get("/api/v1/products?sort=price&limit=2&offset=2")
    assert skus(first.json()).isdisjoint(skus(second.json()))
    assert first.json()["total"] == 4
    assert len(first.json()["items"]) + len(second.json()["items"]) == 4


async def test_offset_past_end(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products?offset=50")
    assert response.json()["items"] == []
    assert response.json()["total"] == 4


async def test_default_listing(client: AsyncClient, catalog: dict) -> None:
    response = await client.get("/api/v1/products")
    body = response.json()
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] == 4


async def test_stable_order_across_equal_prices(
    client: AsyncClient, session: AsyncSession, catalog: dict
) -> None:
    await make_product(session, "EQ-A", catalog["books"], title="Equal A", price="25.00")
    await make_product(session, "EQ-B", catalog["books"], title="Equal B", price="25.00")
    first = await client.get("/api/v1/products?sort=price&limit=2&offset=0")
    second = await client.get("/api/v1/products?sort=price&limit=2&offset=2")
    third = await client.get("/api/v1/products?sort=price&limit=2&offset=4")
    seen: list[str] = []
    for page in (first, second, third):
        seen.extend(item["sku"] for item in page.json()["items"])
    assert len(seen) == len(set(seen))
    again = await client.get("/api/v1/products?sort=price&limit=2&offset=0")
    assert [item["sku"] for item in again.json()["items"]] == [
        item["sku"] for item in first.json()["items"]
    ]


async def test_openapi_documents_search_query_parameters(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    operation = spec["paths"]["/api/v1/products"]["get"]
    names = {param["name"] for param in operation["parameters"]}
    assert names == {
        "q",
        "sku",
        "category_id",
        "include_descendants",
        "price_min",
        "price_max",
        "sort",
        "limit",
        "offset",
    }
    assert operation["summary"] == "List and search products"


@pytest.mark.parametrize(
    "query",
    [
        "price_min=100&price_max=50",
        "price_min=-1",
        "limit=0",
        "limit=1000",
        "offset=-1",
        "sort=secret_field",
        "categoryid=1",
    ],
)
async def test_invalid_parameters_are_rejected(client: AsyncClient, query: str) -> None:
    response = await client.get(f"/api/v1/products?{query}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_trigram_index_exists(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            __import__("sqlalchemy").text(
                "SELECT indexname FROM pg_indexes WHERE indexname = 'ix_products_title_trgm'"
            )
        )
    ).all()
    assert rows


async def test_search_issues_two_queries(
    client: AsyncClient, session: AsyncSession, catalog: dict
) -> None:
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    bind = session.sync_session.get_bind()
    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = await client.get("/api/v1/products?q=phone")
        assert response.status_code == 200
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor_execute)
    assert len(statements) == 2
