from decimal import Decimal

from sqlalchemy.dialects import postgresql

from app.repositories.product_search import ProductFilters, build_count_query, build_search_query


def compiled(filters: ProductFilters):
    return build_search_query(filters).compile(dialect=postgresql.dialect())


def compiled_sql(filters: ProductFilters) -> str:
    return str(compiled(filters))


def test_no_filters_produces_no_where_clause() -> None:
    assert "WHERE" not in compiled_sql(ProductFilters())


def test_price_bounds_are_inclusive() -> None:
    sql = compiled_sql(ProductFilters(price_min=Decimal("10"), price_max=Decimal("20")))
    assert "products.price >=" in sql
    assert "products.price <=" in sql


def test_wildcard_characters_in_q_are_escaped() -> None:
    params = compiled(ProductFilters(q="50%")).params
    assert any("50\\%" in str(value) for value in params.values())


def test_underscore_in_q_is_escaped() -> None:
    params = compiled(ProductFilters(q="a_b")).params
    assert any("a\\_b" in str(value) for value in params.values())


def test_q_matches_title_or_description() -> None:
    sql = compiled_sql(ProductFilters(q="phone"))
    assert "ilike" in sql.lower()
    assert "products.title" in sql
    assert "products.description" in sql


def test_subtree_filter_uses_a_recursive_cte() -> None:
    sql = compiled_sql(ProductFilters(category_id=1, include_descendants=True))
    assert "WITH RECURSIVE" in sql.upper() or "RECURSIVE" in sql.upper()


def test_direct_category_filter_skips_the_cte() -> None:
    sql = compiled_sql(ProductFilters(category_id=1, include_descendants=False))
    assert "RECURSIVE" not in sql.upper()
    assert "products.category_id" in sql


def test_ordering_always_has_an_id_tiebreaker() -> None:
    sql = compiled_sql(ProductFilters(sort="price"))
    assert "products.price" in sql
    assert "products.id" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def test_count_query_shares_filters_and_has_no_limit() -> None:
    count_sql = str(
        build_count_query(ProductFilters(q="phone", price_min=Decimal("10"))).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "count(" in count_sql.lower()
    assert "LIMIT" not in count_sql
    assert "products.price >=" in count_sql


def test_sku_filter_is_uppercased() -> None:
    params = compiled(ProductFilters(sku="smart-1")).params
    assert "SMART-1" in params.values()
