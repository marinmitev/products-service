from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_category, make_product


def error_code(response) -> str:
    return response.json()["error"]["code"]


async def _category(client: AsyncClient) -> int:
    return (await client.post("/api/v1/categories", json={"name": "Gadgets"})).json()["id"]


async def test_create_product(client: AsyncClient) -> None:
    category_id = await _category(client)
    response = await client.post(
        "/api/v1/products",
        json={
            "sku": "smart-1",
            "title": "Smart Phone X",
            "price": "799.00",
            "category_id": category_id,
            "image_url": "https://cdn.example.com/smart-1.jpg",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "SMART-1"
    assert body["price"] == "799.00"
    assert isinstance(body["price"], str)
    assert body["description"] == ""


async def test_duplicate_sku_is_409(client: AsyncClient) -> None:
    category_id = await _category(client)
    payload = {"sku": "DUP-1", "title": "One", "price": "1.00", "category_id": category_id}
    assert (await client.post("/api/v1/products", json=payload)).status_code == 201
    response = await client.post(
        "/api/v1/products",
        json={"sku": "dup-1", "title": "Two", "price": "2.00", "category_id": category_id},
    )
    assert response.status_code == 409
    assert error_code(response) == "duplicate_sku"
    assert "DUP-1" in response.json()["error"]["message"]


async def test_invalid_sku_is_422(client: AsyncClient) -> None:
    category_id = await _category(client)
    response = await client.post(
        "/api/v1/products",
        json={"sku": "!!", "title": "Bad", "price": "1.00", "category_id": category_id},
    )
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_unknown_category_on_create_is_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/products",
        json={"sku": "NOCAT-1", "title": "Ghost", "price": "1.00", "category_id": 99999},
    )
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_negative_price_is_422_zero_is_ok(client: AsyncClient) -> None:
    category_id = await _category(client)
    negative = await client.post(
        "/api/v1/products",
        json={"sku": "NEG-1", "title": "Neg", "price": "-1.00", "category_id": category_id},
    )
    assert negative.status_code == 422
    free = await client.post(
        "/api/v1/products",
        json={"sku": "FREE-1", "title": "Free", "price": "0.00", "category_id": category_id},
    )
    assert free.status_code == 201


async def test_three_decimal_price_is_422(client: AsyncClient) -> None:
    category_id = await _category(client)
    response = await client.post(
        "/api/v1/products",
        json={"sku": "PREC-1", "title": "Precise", "price": "1.999", "category_id": category_id},
    )
    assert response.status_code == 422


async def test_invalid_image_url_is_422(client: AsyncClient) -> None:
    category_id = await _category(client)
    response = await client.post(
        "/api/v1/products",
        json={
            "sku": "IMG-1",
            "title": "Img",
            "price": "1.00",
            "category_id": category_id,
            "image_url": "ftp://files.example.com/x",
        },
    )
    assert response.status_code == 422


async def test_get_and_get_by_sku(client: AsyncClient) -> None:
    category_id = await _category(client)
    created = (
        await client.post(
            "/api/v1/products",
            json={"sku": "LOOK-1", "title": "Look", "price": "10.00", "category_id": category_id},
        )
    ).json()
    by_id = await client.get(f"/api/v1/products/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["sku"] == "LOOK-1"
    by_sku = await client.get("/api/v1/products/by-sku/look-1")
    assert by_sku.status_code == 200
    assert by_sku.json()["id"] == created["id"]
    missing = await client.get("/api/v1/products/99999")
    assert missing.status_code == 404
    assert error_code(missing) == "not_found"


async def test_patch_price_only(client: AsyncClient) -> None:
    category_id = await _category(client)
    created = (
        await client.post(
            "/api/v1/products",
            json={
                "sku": "PATCH-1",
                "title": "Original",
                "description": "keep me",
                "price": "10.00",
                "category_id": category_id,
            },
        )
    ).json()
    response = await client.patch(f"/api/v1/products/{created['id']}", json={"price": "12.50"})
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == "12.50"
    assert body["title"] == "Original"
    assert body["description"] == "keep me"
    assert body["sku"] == "PATCH-1"
    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] >= created["updated_at"]


async def test_patch_sku_is_422(client: AsyncClient) -> None:
    category_id = await _category(client)
    created = (
        await client.post(
            "/api/v1/products",
            json={"sku": "IMM-1", "title": "Imm", "price": "1.00", "category_id": category_id},
        )
    ).json()
    response = await client.patch(f"/api/v1/products/{created['id']}", json={"sku": "IMM-2"})
    assert response.status_code == 422
    assert "immutable" in response.json()["error"]["message"].lower() or any(
        "immutable" in item["message"].lower() for item in response.json()["error"]["details"]
    )


async def test_delete_product(client: AsyncClient) -> None:
    category_id = await _category(client)
    created = (
        await client.post(
            "/api/v1/products",
            json={"sku": "DEL-1", "title": "Del", "price": "1.00", "category_id": category_id},
        )
    ).json()
    first = await client.delete(f"/api/v1/products/{created['id']}")
    assert first.status_code == 204
    second = await client.delete(f"/api/v1/products/{created['id']}")
    assert second.status_code == 404


async def test_error_envelope_on_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/products/by-sku/MISSING-1")
    assert set(response.json()["error"]) == {"code", "message", "details"}


async def test_factory_roundtrip(client: AsyncClient, session: AsyncSession) -> None:
    category = await make_category(session, "Factory")
    product = await make_product(session, "FAC-1", category)
    response = await client.get(f"/api/v1/products/{product.id}")
    assert response.status_code == 200
    assert response.json()["sku"] == "FAC-1"
