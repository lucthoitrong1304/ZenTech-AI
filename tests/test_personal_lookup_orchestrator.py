from app.schemas.agent import AgentRespondRequest, RuntimeAgentConfig
from app.services.context_router import ContextRouteDecision
from app.services.tool_orchestrator import execute_tool_plan


def make_request(
    message: str = "Review sản phẩm này tích cực không?",
    business_context: dict | None = None,
) -> AgentRespondRequest:
    return AgentRespondRequest(
        agent=RuntimeAgentConfig(
            id="agent-1",
            name="ZenTech AI",
            systemPrompt="Trả lời ngắn gọn bằng tiếng Việt.",
        ),
        role="CUSTOMER",
        message=message,
        businessContext=business_context
        or {
            "toolAccessToken": "delegated-token",
            "conversationId": "conversation-1",
            "pageContext": {"currentProductId": "product-1"},
        },
    )


def test_orchestrator_calls_product_review_tool_from_page_context(monkeypatch) -> None:
    calls = []

    def fake_get_product_reviews(product_id, context, page=0, size=5):
        calls.append((product_id, context["toolAccessToken"], size))
        return [{"rating": 5, "comment": "Rất tốt"}]

    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_product_reviews",
        fake_get_product_reviews,
    )

    result = execute_tool_plan(
        make_request(),
        ContextRouteDecision("PRODUCT_QA", ["get_product_reviews"], "test"),
    )

    assert calls == [("product-1", "delegated-token", 5)]
    assert result["product_reviews"][0]["comment"] == "Rất tốt"
    assert "get_product_reviews" in result["tools_executed"]


def test_orchestrator_prefers_resolved_product_over_page_context_for_reviews(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(
        "app.services.tool_orchestrator.search_product_candidates",
        lambda *args, **kwargs: [{"productId": "resolved-product", "variantId": None, "score": 0.95}],
    )
    monkeypatch.setattr(
        "app.services.tool_orchestrator.filter_explicit_product_matches",
        lambda query, candidates: candidates,
    )
    monkeypatch.setattr(
        "app.services.tool_orchestrator.resolve_products",
        lambda product_ids, variant_ids, context: [{"productId": "resolved-product"}],
    )

    def fake_get_product_reviews(product_id, context, page=0, size=5):
        calls.append(product_id)
        return [{"rating": 5, "comment": "Sản phẩm tuyệt vời"}]

    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_product_reviews",
        fake_get_product_reviews,
    )

    result = execute_tool_plan(
        make_request(
            message="Tui muốn tra cứu đánh giá của sản phẩm power strip",
            business_context={
                "toolAccessToken": "delegated-token",
                "conversationId": "conversation-1",
                "pageContext": {"currentProductId": "stale-page-product"},
            },
        ),
        ContextRouteDecision(
            "PRODUCT_QA",
            ["product_search", "resolve_product_candidates", "get_product_reviews"],
            "test",
        ),
    )

    assert calls == ["resolved-product"]
    assert "resolve_product_candidates" in result["tools_executed"]
    assert result["product_reviews"][0]["comment"] == "Sản phẩm tuyệt vời"


def test_personal_tools_without_tool_access_token_mark_auth_required() -> None:
    result = execute_tool_plan(
        make_request(
            message="Địa chỉ giao hàng của tôi là gì?",
            business_context={"conversationId": "conversation-1"},
        ),
        ContextRouteDecision("CUSTOMER_ACCOUNT_QA", ["get_customer_addresses"], "test"),
    )

    assert result["auth_required"] is True
    assert "get_customer_addresses" not in result["tools_executed"]


def test_orchestrator_fetches_sale_products(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_sale_products",
        lambda context, limit=10: [
            {
                "productId": "sale-product",
                "variantId": "sale-variant",
                "name": "Power Strip",
                "price": 990000,
                "originalPrice": 1200000,
                "salePrice": 990000,
            }
        ],
    )

    result = execute_tool_plan(
        make_request(
            message="Có sản phẩm nào đang sale không?",
            business_context={"conversationId": "conversation-1"},
        ),
        ContextRouteDecision("PRODUCT_QA", ["get_sale_products"], "test"),
    )

    assert result["resolved_products"][0]["salePrice"] == 990000
    assert "get_sale_products" in result["tools_executed"]


def test_orchestrator_fetches_catalog_overview(monkeypatch) -> None:
    calls = []

    def fake_get_catalog_overview(context, category_name=None, products_per_category=5, include_empty=True):
        calls.append((category_name, products_per_category, include_empty))
        return {
            "categoryQuery": category_name,
            "categoryMatched": True,
            "categories": [
                {
                    "categoryName": "Keyboards",
                    "activeProductCount": 2,
                    "sampleProducts": [
                        {
                            "productId": "catalog-product",
                            "variantId": "catalog-variant",
                            "name": "Mercury K1",
                            "imageKey": "mercury.webp",
                            "price": 1000000,
                            "stock": 5,
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_catalog_overview",
        fake_get_catalog_overview,
    )

    result = execute_tool_plan(
        make_request(
            message="Cửa hàng có bán bàn phím không?",
            business_context={"conversationId": "conversation-1"},
        ),
        ContextRouteDecision(
            "PRODUCT_QA",
            ["get_catalog_overview"],
            "test",
            category_name="keyboards",
        ),
    )

    assert calls == [("keyboards", 5, True)]
    assert result["catalog_overview"]["categoryMatched"] is True
    assert "get_catalog_overview" in result["tools_executed"]


def test_orchestrator_fetches_all_catalog_products_when_requested(monkeypatch) -> None:
    calls = []

    def fake_get_catalog_overview(context, category_name=None, products_per_category=5, include_empty=True):
        calls.append((category_name, products_per_category, include_empty))
        return {"categoryQuery": category_name, "categoryMatched": True, "categories": []}

    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_catalog_overview",
        fake_get_catalog_overview,
    )

    execute_tool_plan(
        make_request(
            message="show all san pham trong danh muc chargers",
            business_context={"conversationId": "conversation-1"},
        ),
        ContextRouteDecision(
            "PRODUCT_QA",
            ["get_catalog_overview"],
            "test",
            category_name="chargers",
        ),
    )

    assert calls == [("chargers", 100, True)]


def test_orchestrator_uses_requested_catalog_product_count(monkeypatch) -> None:
    calls = []

    def fake_get_catalog_overview(context, category_name=None, products_per_category=5, include_empty=True):
        calls.append((category_name, products_per_category, include_empty))
        return {"categoryQuery": category_name, "categoryMatched": True, "categories": []}

    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_catalog_overview",
        fake_get_catalog_overview,
    )

    execute_tool_plan(
        make_request(
            message="liet ke 10 san pham trong danh muc chargers",
            business_context={"conversationId": "conversation-1"},
        ),
        ContextRouteDecision(
            "PRODUCT_QA",
            ["get_catalog_overview"],
            "test",
            category_name="chargers",
        ),
    )

    assert calls == [("chargers", 10, True)]


def test_orchestrator_suppresses_catalog_recommendations_for_category_mapping(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_catalog_overview",
        lambda *args, **kwargs: {"categories": []},
    )

    result = execute_tool_plan(
        make_request(
            message="Các sản phẩm trên thuộc danh mục nào?",
            business_context={"conversationId": "conversation-1"},
        ),
        ContextRouteDecision("PRODUCT_QA", ["get_catalog_overview"], "test"),
    )

    assert result["suppress_catalog_recommendations"] is True
    assert "get_catalog_overview" in result["tools_executed"]
