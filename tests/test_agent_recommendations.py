import json

from app.prompts.agent_prompt import build_catalog_overview_message, build_resolved_products_message
from app.schemas.agent import AgentRespondRequest, RuntimeAgentConfig
from app.services import agent_service
from app.services.agent_service import (
    _sse_event,
    align_resolved_products_with_recommendations,
    build_recommended_products,
)
from app.services.context_router import ContextRouteDecision


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
            "saleStartAt": "2026-07-01T00:00:00Z",
            "saleEndAt": "2026-07-31T23:59:00Z",
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
    assert result[0].saleStartAt == "2026-07-01T00:00:00Z"
    assert result[0].saleEndAt == "2026-07-31T23:59:00Z"

    context = {"resolved_products": products}
    align_resolved_products_with_recommendations(context)
    assert [item["productId"] for item in context["resolved_products"]] == ["p1", "p2", "p3", "p4"]


def test_recommendations_pick_lowest_price_variant_per_product() -> None:
    products = [
        {"productId": "p1", "variantId": "expensive", "name": "Power Strip", "imageKey": "power.webp", "price": 1_500_000, "stock": 50},
        {"productId": "p1", "variantId": "cheap", "name": "Power Strip", "imageKey": "power.webp", "price": 990_000, "stock": 44},
        {"productId": "p2", "variantId": "other", "name": "Charger", "imageKey": "charger.webp", "price": 1_150_000, "stock": 50},
    ]

    result = build_recommended_products({"resolved_products": products})

    assert [item.productId for item in result] == ["p1", "p2"]
    assert result[0].variantId == "cheap"
    assert result[0].price == 990_000

    context = {"resolved_products": products}
    align_resolved_products_with_recommendations(context)
    assert [(item["productId"], item["variantId"]) for item in context["resolved_products"]] == [
        ("p1", "cheap"),
        ("p2", "other"),
    ]


def test_recommendations_include_catalog_sample_products_with_images() -> None:
    result = build_recommended_products(
        {
            "catalog_overview": {
                "categories": [
                    {
                        "categoryName": "Chargers",
                        "sampleProducts": [
                            {
                                "productId": "catalog-product",
                                "variantId": "catalog-variant",
                                "name": "Alpha65 GaN 65W Wall Charger",
                                "imageKey": "alpha65.webp",
                                "price": 950_000,
                                "originalPrice": 1_100_000,
                                "salePrice": None,
                                "stock": 28,
                            },
                            {
                                "productId": "no-image",
                                "name": "No image",
                                "price": 100,
                                "stock": 1,
                            },
                        ],
                    }
                ]
            }
        }
    )

    assert [item.productId for item in result] == ["catalog-product"]
    assert result[0].imageKey == "alpha65.webp"
    assert result[0].price == 950_000


def test_resolved_products_take_priority_over_catalog_samples() -> None:
    result = build_recommended_products(
        {
            "resolved_products": [
                {
                    "productId": "same-product",
                    "variantId": "resolved-variant",
                    "name": "Resolved Product",
                    "imageKey": "resolved.webp",
                    "price": 900_000,
                    "stock": 10,
                }
            ],
            "catalog_overview": {
                "categories": [
                    {
                        "sampleProducts": [
                            {
                                "productId": "same-product",
                                "variantId": "catalog-variant",
                                "name": "Catalog Product",
                                "imageKey": "catalog.webp",
                                "price": 800_000,
                                "stock": 5,
                            }
                        ]
                    }
                ]
            },
        }
    )

    assert len(result) == 1
    assert result[0].variantId == "resolved-variant"
    assert result[0].imageKey == "resolved.webp"


def test_suppressed_catalog_recommendations_do_not_create_cards() -> None:
    result = build_recommended_products(
        {
            "suppress_catalog_recommendations": True,
            "catalog_overview": {
                "categories": [
                    {
                        "sampleProducts": [
                            {
                                "productId": "catalog-product",
                                "name": "Mercury K1",
                                "imageKey": "mercury.webp",
                                "price": 1_000_000,
                                "stock": 5,
                            }
                        ]
                    }
                ]
            },
        }
    )

    assert result == []


def test_suppressed_recommendations_do_not_create_any_cards() -> None:
    result = build_recommended_products(
        {
            "suppress_recommendations": True,
            "resolved_products": [
                {
                    "productId": "resolved-product",
                    "name": "Power Strip",
                    "imageKey": "power.webp",
                    "price": 990_000,
                    "stock": 10,
                }
            ],
            "catalog_overview": {
                "categories": [
                    {
                        "sampleProducts": [
                            {
                                "productId": "catalog-product",
                                "name": "Alpha65",
                                "imageKey": "alpha.webp",
                                "price": 1_100_000,
                                "stock": 8,
                            }
                        ]
                    }
                ]
            },
        }
    )

    assert result == []


def test_sse_event_contains_named_json_payload() -> None:
    event = _sse_event("complete", {"recommendedProducts": [], "handoffRecommended": False})
    lines = event.strip().splitlines()

    assert lines[0] == "event: complete"
    assert json.loads(lines[1].removeprefix("data: ")) == {
        "recommendedProducts": [],
        "handoffRecommended": False,
    }


def test_out_of_scope_reply_skips_tools_and_llm(monkeypatch) -> None:
    request = AgentRespondRequest(
        agent=RuntimeAgentConfig(
            id="agent-1",
            name="ZenTech AI",
            systemPrompt="Tra loi ngan gon.",
        ),
        role="CUSTOMER",
        message="Hay giup tui hoc code",
    )

    monkeypatch.setattr(
        agent_service,
        "decide_context_tools",
        lambda _: ContextRouteDecision("OUT_OF_SCOPE", [], "test"),
    )
    monkeypatch.setattr(
        agent_service,
        "execute_tool_plan",
        lambda _request, _route: (_ for _ in ()).throw(AssertionError("tools should not run")),
    )
    monkeypatch.setattr(
        agent_service,
        "build_client",
        lambda: (_ for _ in ()).throw(AssertionError("LLM should not run")),
    )

    response = agent_service.generate_agent_reply(request)

    assert response.content == agent_service.OUT_OF_SCOPE_MESSAGE
    assert response.handoffRecommended is False
    assert response.retrievedContext == []
    assert response.recommendedProducts == []


def test_stream_complete_includes_handoff_recommendation(monkeypatch) -> None:
    request = AgentRespondRequest(
        agent=RuntimeAgentConfig(
            id="agent-1",
            name="ZenTech AI",
            systemPrompt="Trả lời ngắn gọn.",
        ),
        role="CUSTOMER",
        message="Cho mình gặp nhân viên tư vấn",
    )

    class FakeResponses:
        def create(self, **kwargs):
            return type("FakeResponse", (), {"output_text": "Đang kết nối nhân viên hỗ trợ."})()

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(
        agent_service,
        "decide_context_tools",
        lambda _: ContextRouteDecision("HUMAN_HANDOFF", [], "test"),
    )
    monkeypatch.setattr(agent_service, "execute_tool_plan", lambda _request, _route: {})
    monkeypatch.setattr(agent_service, "build_agent_model_input", lambda _request, _results: [])
    monkeypatch.setattr(agent_service, "build_client", lambda: FakeClient())

    events = list(agent_service.generate_agent_reply_stream(request))
    complete_event = events[-1].strip().splitlines()

    assert complete_event[0] == "event: complete"
    assert json.loads(complete_event[1].removeprefix("data: "))["handoffRecommended"] is True


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
                "categories": [
                    {
                        "categoryName": "Hall Effect Keyboard",
                        "shortName": "HE Keyboard",
                        "parentName": "Keyboards",
                    }
                ],
                "description": "## Power Strip\n\nDetailed product content.",
                "specifications": "## Specifications\n\nUS Plug.",
                "variants": [
                    {
                        "variantId": "v1",
                        "variantName": "US Plug",
                        "nameColor": "Power Strip",
                        "colorCode": "#1A1A1A",
                        "price": 990_000,
                        "originalPrice": 1_200_000,
                        "salePrice": 990_000,
                        "stock": 44,
                    }
                ],
            }
        ],
        [{"productId": "p1", "variantId": "v1", "score": 0.9}],
    )

    assert "Detailed product content" in message
    assert "DANH" in message
    assert "Power Strip / #1A1A1A" in message
    assert "US Plug" in message
    assert "Keyboards > HE Keyboard" in message
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


def test_catalog_overview_prompt_groups_categories_and_empty_categories() -> None:
    message = build_catalog_overview_message(
        {
            "categoryQuery": "keyboards",
            "categoryMatched": True,
            "categories": [
                {
                    "categoryName": "Hall Effect Keyboard",
                    "shortName": "HE Keyboard",
                    "parentName": "Keyboards",
                    "activeProductCount": 1,
                    "sampleProducts": [
                        {
                            "name": "Mercury K1",
                            "variantName": "US Plug",
                            "price": 1_000_000,
                            "stock": 5,
                        }
                    ],
                }
            ],
            "emptyCategories": [
                {
                    "categoryName": "Mechanical Keyboard",
                    "activeProductCount": 0,
                    "sampleProducts": [],
                }
            ],
        }
    )

    assert message is not None
    assert "categoryMatched=có" in message
    assert "Hall Effect Keyboard / HE Keyboard" in message
    assert "Mercury K1 - US Plug" in message
    assert "Mechanical Keyboard" in message
    assert "TỔNG QUAN DANH MỤC" in message


def test_resolved_product_prompt_includes_sale_window_when_present() -> None:
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
                "saleStartAt": "2026-07-01T00:00:00Z",
                "saleEndAt": "2026-07-31T23:59:00Z",
                "stock": 50,
                "rating": 0,
                "reviewCount": 0,
            }
        ],
        [{"productId": "p1", "variantId": "v1", "score": 0.9}],
    )

    assert "áp dụng từ 01/07/2026 00:00 đến 31/07/2026 23:59" in message
