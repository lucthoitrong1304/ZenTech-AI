import json
import logging
from typing import Generator

from app.config import settings
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

logger = logging.getLogger("ai-service")


def build_recommended_products(orchestrator_results: dict) -> list[RecommendedProductResponse]:
    recommendations: list[RecommendedProductResponse] = []
    seen_product_ids: set[str] = set()

    for product in orchestrator_results.get("resolved_products", []):
        product_id = str(product.get("productId") or "").strip()
        image_key = str(product.get("imageKey") or "").strip()
        if not product_id or not image_key or product_id in seen_product_ids:
            continue

        recommendations.append(
            RecommendedProductResponse(
                productId=product_id,
                variantId=str(product["variantId"]) if product.get("variantId") else None,
                name=str(product.get("name") or ""),
                imageKey=image_key,
                price=float(product.get("price") or 0),
                stock=int(product.get("stock") or 0),
            )
        )
        seen_product_ids.add(product_id)

    return recommendations
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
    recommendation_ids = {
        item.productId for item in build_recommended_products(orchestrator_results)
    }
    seen_product_ids: set[str] = set()
    aligned_products = []

    for product in orchestrator_results.get("resolved_products", []):
        product_id = str(product.get("productId") or "").strip()
        if product_id in recommendation_ids and product_id not in seen_product_ids:
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
    logger.info("Generating agent reply for user request: %s", request.message)
    route = decide_context_tools(request)
    orchestrator_results = execute_tool_plan(request, route)
    extract_and_append_related_products(request, orchestrator_results)
    align_resolved_products_with_recommendations(orchestrator_results)
    recommendations = build_recommended_products(orchestrator_results)
    messages = build_agent_model_input(request, orchestrator_results)

    client = build_client()
    try:
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

        return AgentRespondResponse(
            content=content,
            fallback=False,
            handoffRecommended=(route.intent == "HUMAN_HANDOFF"),
            retrievedContext=_retrieved_context(orchestrator_results),
            recommendedProducts=recommendations,
        )
    except Exception as ex:
        logger.error("Error calling LLM: %s", ex)
        return AgentRespondResponse(
            content=request.agent.fallbackMessage or "Tôi chưa có đủ thông tin để trả lời câu hỏi này.",
            fallback=True,
            handoffRecommended=True,
            retrievedContext=[],
            recommendedProducts=recommendations,
        )


def generate_agent_reply_stream(request: AgentRespondRequest) -> Generator[str, None, None]:
    logger.info("Generating streaming agent reply for: %s", request.message)
    recommendations: list[RecommendedProductResponse] = []
    try:
        route = decide_context_tools(request)
        orchestrator_results = execute_tool_plan(request, route)
        extract_and_append_related_products(request, orchestrator_results)
        align_resolved_products_with_recommendations(orchestrator_results)
        recommendations = build_recommended_products(orchestrator_results)
        messages = build_agent_model_input(request, orchestrator_results)
        client = build_client()
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
    except Exception as ex:
        logger.error("Error calling LLM stream: %s", ex)
        fallback = request.agent.fallbackMessage or "Tôi chưa có đủ thông tin để trả lời câu hỏi này."
        yield _sse_event("chunk", {"content": fallback})
    finally:
        yield _sse_event(
            "complete",
            {"recommendedProducts": [item.model_dump() for item in recommendations]},
        )
