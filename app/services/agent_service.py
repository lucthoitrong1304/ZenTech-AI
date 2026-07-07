import json
import logging
from typing import Generator

from app.config import settings
from app.core.logging_utils import truncate_text
from app.prompts.agent_prompt import build_agent_model_input
from app.schemas.agent import (
    AgentRespondRequest,
    AgentRespondResponse,
    RecommendedProductResponse,
    RetrievedContextResponse,
)
from app.services.context_router import decide_context_tools
from app.services.openai_client import build_client
from app.services.tool_orchestrator import execute_tool_plan

logger = logging.getLogger("ai-service.agent")
llm_logger = logging.getLogger("ai-service.llm")

OUT_OF_SCOPE_MESSAGE = (
    "Xin lỗi, ZenTech AI chỉ hỗ trợ các vấn đề liên quan đến sản phẩm, đơn hàng, "
    "khuyến mãi, bảo hành, vận chuyển và dịch vụ của ZenTech. Mình chưa thể hỗ trợ "
    "chủ đề này. Bạn có thể hỏi mình về sản phẩm, danh mục, giá, tồn kho hoặc đơn hàng nhé."
)


def build_recommended_products(orchestrator_results: dict) -> list[RecommendedProductResponse]:
    if orchestrator_results.get("suppress_recommendations"):
        return []

    products_by_id: dict[str, dict] = {}

    for product in orchestrator_results.get("resolved_products", []):
        product_id = str(product.get("productId") or "").strip()
        image_key = str(product.get("imageKey") or "").strip()
        if not product_id or not image_key:
            continue
        current = products_by_id.get(product_id)
        if current is None or _effective_price(product) < _effective_price(current):
            products_by_id[product_id] = product

    if not orchestrator_results.get("suppress_catalog_recommendations"):
        for product in _catalog_sample_products(orchestrator_results.get("catalog_overview")):
            product_id = str(product.get("productId") or "").strip()
            image_key = str(product.get("imageKey") or "").strip()
            if not product_id or not image_key or product_id in products_by_id:
                continue
            products_by_id[product_id] = product

    recommendations: list[RecommendedProductResponse] = []
    for product_id, product in products_by_id.items():
        image_key = str(product.get("imageKey") or "").strip()

        recommendations.append(
            RecommendedProductResponse(
                productId=product_id,
                variantId=str(product["variantId"]) if product.get("variantId") else None,
                name=str(product.get("name") or ""),
                imageKey=image_key,
                price=float(product.get("price") or 0),
                originalPrice=float(product["originalPrice"]) if product.get("originalPrice") is not None else None,
                salePrice=float(product["salePrice"]) if product.get("salePrice") is not None else None,
                saleStartAt=str(product["saleStartAt"]) if product.get("saleStartAt") else None,
                saleEndAt=str(product["saleEndAt"]) if product.get("saleEndAt") else None,
                stock=int(product.get("stock") or 0),
            )
        )

    return recommendations


def _catalog_sample_products(catalog_overview: object) -> list[dict]:
    if not isinstance(catalog_overview, dict):
        return []

    products: list[dict] = []
    categories = catalog_overview.get("categories") or []
    if not isinstance(categories, list):
        return products

    for category in categories:
        if not isinstance(category, dict):
            continue
        sample_products = category.get("sampleProducts") or []
        if not isinstance(sample_products, list):
            continue
        for product in sample_products:
            if isinstance(product, dict):
                products.append(product)

    return products


def _effective_price(product: dict) -> float:
    try:
        return float(product.get("price") or 0)
    except (TypeError, ValueError):
        return 0.0


def _variant_key(product: dict) -> tuple[str, str | None]:
    product_id = str(product.get("productId") or "").strip()
    variant_id = product.get("variantId")
    return product_id, str(variant_id) if variant_id else None


def extract_and_append_related_products(request: AgentRespondRequest, orchestrator_results: dict) -> None:
    message_lower = request.message.lower()
    keywords = ["liên quan", "tương tự", "khác", "cùng nhóm", "related", "similar", "alternative"]
    is_related_query = any(kw in message_lower for kw in keywords)
    
    if not is_related_query:
        return
        
    resolved = orchestrator_results.get("resolved_products", [])
    if not resolved:
        return
        
    new_products = list(resolved)
    seen_ids = {str(p.get("productId") or "").strip() for p in resolved}
    
    for product in resolved:
        related_list = product.get("relatedProductList") or []
        for item in related_list:
            prod_id = str(item.get("productId") or "").strip()
            if prod_id and prod_id not in seen_ids:
                new_products.append({
                    "productId": prod_id,
                    "variantId": item.get("variantId"),
                    "name": item.get("name"),
                    "variantName": item.get("variantName"),
                    "price": float(item.get("price") or 0),
                    "originalPrice": float(item["originalPrice"]) if item.get("originalPrice") is not None else None,
                    "salePrice": float(item["salePrice"]) if item.get("salePrice") is not None else None,
                    "saleStartAt": item.get("saleStartAt"),
                    "saleEndAt": item.get("saleEndAt"),
                    "stock": int(item.get("stock") or 0),
                    "imageKey": item.get("imageKey"),
                    "description": "",
                    "specifications": "",
                    "compatibility": "",
                    "boxContents": "",
                    "supportInfo": ""
                })
                seen_ids.add(prod_id)
                
    orchestrator_results["resolved_products"] = new_products


def align_resolved_products_with_recommendations(orchestrator_results: dict) -> None:
    if orchestrator_results.get("catalog_overview") or orchestrator_results.get("suppress_recommendations"):
        return

    recommendation_keys = {
        (item.productId, item.variantId) for item in build_recommended_products(orchestrator_results)
    }
    seen_product_ids: set[str] = set()
    aligned_products = []

    for product in orchestrator_results.get("resolved_products", []):
        product_id = str(product.get("productId") or "").strip()
        if _variant_key(product) in recommendation_keys and product_id not in seen_product_ids:
            aligned_products.append(product)
            seen_product_ids.add(product_id)

    orchestrator_results["resolved_products"] = aligned_products


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _retrieved_context(orchestrator_results: dict) -> list[RetrievedContextResponse]:
    return [
        RetrievedContextResponse(
            id=str(item.id),
            content=item.content,
            score=item.score,
            source=item.source,
            datasetId=item.datasetId,
            documentId=item.documentId,
        )
        for item in orchestrator_results.get("knowledge_context", [])
    ]


def generate_agent_reply(request: AgentRespondRequest) -> AgentRespondResponse:
    logger.info(
        "Received agent analysis request: agent_id=%s dataset_count=%s message_preview='%s'",
        request.agent.id,
        len(request.datasetIds),
        truncate_text(request.message, 150),
    )
    route = decide_context_tools(request)
    logger.info("Agent route selected: intent=%s tools=%s", route.intent, route.tools)
    if route.intent == "OUT_OF_SCOPE":
        return AgentRespondResponse(
            content=OUT_OF_SCOPE_MESSAGE,
            fallback=False,
            handoffRecommended=False,
            retrievedContext=[],
            recommendedProducts=[],
        )

    orchestrator_results = execute_tool_plan(request, route)
    extract_and_append_related_products(request, orchestrator_results)
    align_resolved_products_with_recommendations(orchestrator_results)
    recommendations = build_recommended_products(orchestrator_results)
    messages = build_agent_model_input(request, orchestrator_results)

    client = build_client()
    try:
        llm_logger.info("Starting LLM call for agent reply: model=%s intent=%s", settings.chat_deployment_name, route.intent)
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.chat_deployment_name,
                messages=messages,
                temperature=request.agent.temperature,
                max_completion_tokens=request.agent.maxTokens,
            )
            content = response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=settings.chat_deployment_name,
                input=messages,
            )
            content = response.output_text.strip()

        llm_logger.info("LLM call completed for agent reply: response_length=%s", len(content))
        logger.info(
            "Agent analysis completed: intent=%s contexts=%s recommendations=%s",
            route.intent,
            len(orchestrator_results.get("knowledge_context", [])),
            len(recommendations),
        )
        return AgentRespondResponse(
            content=content,
            fallback=False,
            handoffRecommended=(route.intent == "HUMAN_HANDOFF"),
            retrievedContext=_retrieved_context(orchestrator_results),
            recommendedProducts=recommendations,
        )
    except Exception:
        llm_logger.error("Error calling LLM for agent reply", exc_info=True)
        return AgentRespondResponse(
            content=request.agent.fallbackMessage or "Tôi chưa có đủ thông tin để trả lời câu hỏi này.",
            fallback=True,
            handoffRecommended=True,
            retrievedContext=[],
            recommendedProducts=recommendations,
        )


def generate_agent_reply_stream(request: AgentRespondRequest) -> Generator[str, None, None]:
    logger.info(
        "Received streaming agent analysis request: agent_id=%s dataset_count=%s message_preview='%s'",
        request.agent.id,
        len(request.datasetIds),
        truncate_text(request.message, 150),
    )
    recommendations: list[RecommendedProductResponse] = []
    handoff_recommended = False
    try:
        route = decide_context_tools(request)
        handoff_recommended = route.intent == "HUMAN_HANDOFF"
        logger.info("Streaming agent route selected: intent=%s tools=%s", route.intent, route.tools)
        if route.intent == "OUT_OF_SCOPE":
            yield _sse_event("chunk", {"content": OUT_OF_SCOPE_MESSAGE})
            return

        orchestrator_results = execute_tool_plan(request, route)
        extract_and_append_related_products(request, orchestrator_results)
        align_resolved_products_with_recommendations(orchestrator_results)
        recommendations = build_recommended_products(orchestrator_results)
        messages = build_agent_model_input(request, orchestrator_results)
        client = build_client()
        llm_logger.info("Starting streaming LLM call: model=%s intent=%s", settings.chat_deployment_name, route.intent)
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.chat_deployment_name,
                messages=messages,
                temperature=request.agent.temperature,
                max_completion_tokens=request.agent.maxTokens,
                stream=True,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield _sse_event("chunk", {"content": chunk.choices[0].delta.content})
        else:
            response = client.responses.create(
                model=settings.chat_deployment_name,
                input=messages,
            )
            yield _sse_event("chunk", {"content": response.output_text})
        llm_logger.info("Streaming LLM call completed")
        logger.info("Streaming agent analysis completed: recommendations=%s", len(recommendations))
    except Exception:
        llm_logger.error("Error calling streaming LLM", exc_info=True)
        fallback = request.agent.fallbackMessage or "Tôi chưa có đủ thông tin để trả lời câu hỏi này."
        handoff_recommended = True
        yield _sse_event("chunk", {"content": fallback})
    finally:
        yield _sse_event(
            "complete",
            {
                "recommendedProducts": [item.model_dump() for item in recommendations],
                "handoffRecommended": handoff_recommended,
            },
        )
