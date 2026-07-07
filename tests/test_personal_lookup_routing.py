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
    route = decide_context_tools(make_request("Có sản phẩm nào đang sale không?"))

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["get_sale_products"]


def test_learning_code_routes_out_of_scope_without_llm() -> None:
    route = decide_context_tools(make_request("Hay giup tui hoc code"))

    assert route.intent == "OUT_OF_SCOPE"
    assert route.tools == []


def test_food_chat_routes_out_of_scope_without_llm() -> None:
    route = decide_context_tools(make_request("Bun bo ngon qua"))

    assert route.intent == "OUT_OF_SCOPE"
    assert route.tools == []


def test_learning_python_routes_out_of_scope_without_llm() -> None:
    route = decide_context_tools(make_request("Day tui Python"))

    assert route.intent == "OUT_OF_SCOPE"
    assert route.tools == []


def test_product_comparison_routes_without_recommendations() -> None:
    route = decide_context_tools(make_request("compare Power Strip voi Alpha65"))

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["product_search", "resolve_product_candidates"]
    assert route.suppress_recommendations is True


def test_catalog_overview_lookup_routes_without_llm() -> None:
    route = decide_context_tools(make_request("Cho tui hỏi các mặt hàng mà cửa hàng mình kinh doanh?"))

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["get_catalog_overview"]
    assert route.category_name is None


def test_category_availability_lookup_extracts_keyboard_category() -> None:
    route = decide_context_tools(make_request("Cho tui hỏi cửa hàng mình có bán bàn phím không?"))

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["get_catalog_overview"]
    assert route.category_name == "keyboards"


def test_product_category_followup_uses_catalog_overview() -> None:
    route = decide_context_tools(make_request("Các sản phẩm trên thuộc danh mục nào của cửa hàng?"))

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["get_catalog_overview"]


def test_category_product_listing_extracts_chargers_category() -> None:
    route = decide_context_tools(make_request("Liệt kê các sản phẩm khác trong danh mục chargers"))

    assert route.intent == "PRODUCT_QA"
    assert route.tools == ["get_catalog_overview"]
    assert route.category_name == "chargers"


def test_simple_thanks_still_routes_small_talk() -> None:
    route = decide_context_tools(make_request("cam on"))

    assert route.intent == "SMALL_TALK"
    assert route.tools == []


def test_human_handoff_routes_without_llm() -> None:
    route = decide_context_tools(make_request("Cho mình gặp nhân viên tư vấn"))

    assert route.intent == "HUMAN_HANDOFF"
    assert route.tools == []
