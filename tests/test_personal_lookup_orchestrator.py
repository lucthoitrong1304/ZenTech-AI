from app.schemas.agent import AgentRespondRequest, RuntimeAgentConfig
from app.services.context_router import ContextRouteDecision
from app.services.tool_orchestrator import execute_tool_plan


def make_request() -> AgentRespondRequest:
    return AgentRespondRequest(
        agent=RuntimeAgentConfig(
            id="agent-1",
            name="ZenTech AI",
            systemPrompt="Tra loi ngan gon bang tieng Viet.",
        ),
        role="CUSTOMER",
        message="Review sản phẩm này tích cực không?",
        businessContext={
            "userId": "account-1",
            "conversationId": "conversation-1",
            "pageContext": {"currentProductId": "product-1"},
        },
    )


def test_orchestrator_calls_product_review_tool_from_page_context(monkeypatch) -> None:
    calls = []

    def fake_get_product_reviews(product_id, context, page=0, size=5):
        calls.append((product_id, context["userId"], size))
        return [{"rating": 5, "comment": "Rất tốt"}]

    monkeypatch.setattr(
        "app.services.tool_orchestrator.get_product_reviews",
        fake_get_product_reviews,
    )

    result = execute_tool_plan(
        make_request(),
        ContextRouteDecision("PRODUCT_QA", ["get_product_reviews"], "test"),
    )

    assert calls == [("product-1", "account-1", 5)]
    assert result["product_reviews"][0]["comment"] == "Rất tốt"
    assert "get_product_reviews" in result["tools_executed"]
