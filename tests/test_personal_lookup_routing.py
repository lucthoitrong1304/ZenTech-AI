from app.schemas.agent import AgentRespondRequest, RuntimeAgentConfig
from app.services.context_router import decide_context_tools


def make_request(message: str, business_context: dict | None = None) -> AgentRespondRequest:
    return AgentRespondRequest(
        agent=RuntimeAgentConfig(
            id="agent-1",
            name="ZenTech AI",
            systemPrompt="Trả lời ngắn gọn bằng tiếng Việt.",
        ),
        role="CUSTOMER",
        message=message,
        businessContext=business_context or {},
    )


def test_order_lookup_routes_without_llm() -> None:
    route = decide_context_tools(make_request("Tui muốn tra cứu đơn hàng của mình"))

    assert route.intent == "ORDER_QA"
    assert "get_customer_orders" in route.tools


def test_voucher_lookup_routes_without_llm() -> None:
    route = decide_context_tools(make_request("Voucher của tôi còn cái nào dùng được không?"))

    assert route.intent == "PROMOTION_QA"
    assert "get_customer_vouchers" in route.tools


def test_product_review_lookup_uses_page_context() -> None:
    route = decide_context_tools(
        make_request(
            "2 đánh giá sản phẩm trên có tích cực không?",
            {"pageContext": {"currentProductId": "product-1"}},
        )
    )

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["get_product_reviews"]


def test_product_review_lookup_with_explicit_name_searches_even_with_page_context() -> None:
    route = decide_context_tools(
        make_request(
            "Tui muốn tra cứu đánh giá của sản phẩm power strip",
            {"pageContext": {"currentProductId": "currently-open-product"}},
        )
    )

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["product_search", "resolve_product_candidates", "get_product_reviews"]


def test_address_lookup_routes_without_llm() -> None:
    route = decide_context_tools(make_request("Địa chỉ giao hàng mặc định của tôi là gì?"))

    assert route.intent == "CUSTOMER_ACCOUNT_QA"
    assert route.tools == ["get_customer_addresses"]


def test_profile_lookup_routes_without_llm() -> None:
    route = decide_context_tools(make_request("Thông tin cá nhân của tôi gồm những gì?"))

    assert route.intent == "CUSTOMER_ACCOUNT_QA"
    assert route.tools == ["get_customer_profile"]


def test_sale_product_lookup_routes_without_llm() -> None:
    route = decide_context_tools(make_request("Co san pham nao dang sale ko?"))

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["get_sale_products"]
