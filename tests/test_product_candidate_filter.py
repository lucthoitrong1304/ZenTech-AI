from app.services.product_search_service import filter_explicit_product_matches


CANDIDATES = [
    {"productId": "alpha-yellow", "name": "Alpha65 GaN 65W Wall Charger - War Damaged Yellow"},
    {"productId": "power-strip", "name": "Power Strip"},
    {"productId": "bundle", "name": "Alpha65 & Power Strip Bundle"},
]


def test_exact_product_name_excludes_related_candidates() -> None:
    result = filter_explicit_product_matches(
        "Cho tui biết thông tin chi tiết của sản phẩm Power Strip",
        CANDIDATES,
    )

    assert [item["productId"] for item in result] == ["power-strip"]


def test_longest_explicit_name_wins_for_bundle() -> None:
    result = filter_explicit_product_matches(
        "Mô tả Alpha65 & Power Strip Bundle",
        CANDIDATES,
    )

    assert [item["productId"] for item in result] == ["bundle"]


def test_broad_category_query_keeps_semantic_results() -> None:
    result = filter_explicit_product_matches("Các sản phẩm chargers đang bán", CANDIDATES)

    assert result == CANDIDATES
