import json

from app.prompts.agent_prompt import build_resolved_products_message
from app.services.agent_service import (
    _sse_event,
    align_resolved_products_with_recommendations,
    build_recommended_products,
)


def test_recommendations_require_image_and_dedupe_without_truncating() -> None:
    products = [
        {"productId": "p0", "name": "No image", "price": 1, "stock": 1},
        {
            "productId": "p1",
            "variantId": "v1",
            "name": "One",
            "imageKey": "one.webp",
            "price": 10,
            "originalPrice": 12,
            "salePrice": 10,
            "stock": 2,
        },
        {"productId": "p1", "variantId": "v2", "name": "Duplicate", "imageKey": "duplicate.webp", "price": 20, "stock": 3},
        {"productId": "p2", "name": "Two", "imageKey": "two.webp", "price": 30, "stock": 4},
        {"productId": "p3", "name": "Three", "imageKey": "three.webp", "price": 40, "stock": 5},
        {"productId": "p4", "name": "Four", "imageKey": "four.webp", "price": 50, "stock": 6},
    ]

    result = build_recommended_products({"resolved_products": products})

    assert [item.productId for item in result] == ["p1", "p2", "p3", "p4"]
    assert result[0].variantId == "v1"
    assert result[0].originalPrice == 12
    assert result[0].salePrice == 10

    context = {"resolved_products": products}
    align_resolved_products_with_recommendations(context)
    assert [item["productId"] for item in context["resolved_products"]] == ["p1", "p2", "p3", "p4"]


def test_sse_event_contains_named_json_payload() -> None:
    event = _sse_event("complete", {"recommendedProducts": []})
    lines = event.strip().splitlines()

    assert lines[0] == "event: complete"
    assert json.loads(lines[1].removeprefix("data: ")) == {"recommendedProducts": []}


def test_resolved_product_prompt_includes_markdown_details_and_sale_price() -> None:
    message = build_resolved_products_message(
        [
            {
                "productId": "p1",
                "variantId": "v1",
                "name": "Power Strip",
                "variantName": "US Plug",
                "sku": "",
                "price": 990_000,
                "originalPrice": 1_200_000,
                "salePrice": 990_000,
                "stock": 50,
                "rating": 0,
                "reviewCount": 0,
                "description": "## Power Strip\n\nDetailed product content.",
                "specifications": "## Specifications\n\nUS Plug.",
            }
        ],
        [{"productId": "p1", "variantId": "v1", "score": 0.9}],
    )

    assert "Detailed product content" in message
    assert "US Plug" in message
    assert "MÔ TẢ CHI TIẾT" in message
    assert "Giá sale hiện tại: 990,000 VND (giá gốc: 1,200,000 VND)" in message


def test_resolved_product_prompt_omits_original_price_without_sale() -> None:
    message = build_resolved_products_message(
        [
            {
                "productId": "p1",
                "variantId": "v1",
                "name": "Power Strip",
                "variantName": "US Plug",
                "sku": "",
                "price": 1_200_000,
                "originalPrice": 1_200_000,
                "salePrice": None,
                "stock": 50,
                "rating": 0,
                "reviewCount": 0,
            }
        ],
        [{"productId": "p1", "variantId": "v1", "score": 0.9}],
    )

    assert "Giá hiện tại: 1,200,000 VND" in message
    assert "giá gốc" not in message
