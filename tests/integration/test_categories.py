from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_category, make_product


def error_code(response) -> str:
    return response.json()["error"]["code"]


async def test_create_root_category(client: AsyncClient) -> None:
    response = await client.post("/api/v1/categories", json={"name": "Electronics"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Electronics"
    assert body["parent_id"] is None


async def test_create_trims_name(client: AsyncClient) -> None:
    response = await client.post("/api/v1/categories", json={"name": "  Phones  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Phones"


async def test_unknown_parent_is_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/categories", json={"name": "Orphan", "parent_id": 99999})
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_duplicate_sibling_name_is_409(client: AsyncClient) -> None:
    first = await client.post("/api/v1/categories", json={"name": "Books"})
    parent_id = first.json()["id"]
    await client.post("/api/v1/categories", json={"name": "Fiction", "parent_id": parent_id})
    response = await client.post(
        "/api/v1/categories", json={"name": "Fiction", "parent_id": parent_id}
    )
    assert response.status_code == 409
    assert error_code(response) == "duplicate_category_name"


async def test_list_direct_children(client: AsyncClient) -> None:
    parent = (await client.post("/api/v1/categories", json={"name": "Parent"})).json()
    await client.post("/api/v1/categories", json={"name": "Child", "parent_id": parent["id"]})
    await client.post("/api/v1/categories", json={"name": "OtherRoot"})
    response = await client.get(f"/api/v1/categories?parent_id={parent['id']}")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"Child"}


async def test_get_unknown_category_is_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/categories/99999")
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert response.json()["error"]["details"] == []


async def test_self_parent_is_cycle(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/categories", json={"name": "Self"})).json()
    response = await client.patch(
        f"/api/v1/categories/{created['id']}", json={"parent_id": created["id"]}
    )
    assert response.status_code == 409
    assert error_code(response) == "category_cycle"


async def test_reparent_to_descendant_is_cycle(client: AsyncClient) -> None:
    a = (await client.post("/api/v1/categories", json={"name": "A"})).json()
    b = (await client.post("/api/v1/categories", json={"name": "B", "parent_id": a["id"]})).json()
    c = (await client.post("/api/v1/categories", json={"name": "C", "parent_id": b["id"]})).json()
    response = await client.patch(f"/api/v1/categories/{a['id']}", json={"parent_id": c["id"]})
    assert response.status_code == 409
    assert error_code(response) == "category_cycle"


async def test_patch_name_leaves_parent(client: AsyncClient) -> None:
    parent = (await client.post("/api/v1/categories", json={"name": "KeepParent"})).json()
    child = (
        await client.post("/api/v1/categories", json={"name": "Old", "parent_id": parent["id"]})
    ).json()
    response = await client.patch(f"/api/v1/categories/{child['id']}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"
    assert response.json()["parent_id"] == parent["id"]


async def test_delete_blocked_by_children(client: AsyncClient) -> None:
    parent = (await client.post("/api/v1/categories", json={"name": "HasKids"})).json()
    await client.post("/api/v1/categories", json={"name": "Kid", "parent_id": parent["id"]})
    response = await client.delete(f"/api/v1/categories/{parent['id']}")
    assert response.status_code == 409
    assert error_code(response) == "category_not_empty"
    assert "child" in response.json()["error"]["message"]


async def test_delete_blocked_by_products(client: AsyncClient, session: AsyncSession) -> None:
    category = await make_category(session, "HasProducts")
    await make_product(session, "HAS-1", category)
    response = await client.delete(f"/api/v1/categories/{category.id}")
    assert response.status_code == 409
    assert error_code(response) == "category_not_empty"
    assert "product" in response.json()["error"]["message"]


async def test_delete_empty_leaf(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/categories", json={"name": "Leaf"})).json()
    response = await client.delete(f"/api/v1/categories/{created['id']}")
    assert response.status_code == 204
    assert (await client.get(f"/api/v1/categories/{created['id']}")).status_code == 404
