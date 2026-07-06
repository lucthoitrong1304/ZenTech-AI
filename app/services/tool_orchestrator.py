import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

from app.core.logging_utils import truncate_text
from app.schemas.agent import AgentRespondRequest
from app.services.context_router import ContextRouteDecision
from app.services.db_tool_client import (
    get_catalog_overview,
    get_customer_addresses,
    get_customer_profile,
    get_customer_vouchers,
    get_customer_orders,
    get_loyalty_points,
    get_order_tracking,
    get_product_reviews,
    get_promotions,
    get_sale_products,
    get_return_requests,
    get_warranty_status,
    resolve_orders,
    resolve_products,
)
from app.services.image_analysis_service import analyze_product_image
from app.services.knowledge_search_service import search_knowledge
from app.services.product_search_service import filter_explicit_product_matches, search_product_candidates

logger = logging.getLogger("ai-service.tool-orchestrator")


def extract_identifier(text: str) -> Optional[str]:
    # Match UUIDs (standard for primary keys)
    uuid_match = re.search(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", text)
    if uuid_match:
        return uuid_match.group(0)
    # Match generic order codes (alphanumeric, length 6-15, e.g. ORD123456, ZT-892341)
    code_match = re.search(r"\b(ORD|ZT|ORDER)?-?([A-Za-z0-9]{6,15})\b", text, re.IGNORECASE)
    if code_match:
        return code_match.group(0)
    return None


def execute_tool_plan(request: AgentRespondRequest, decision: ContextRouteDecision) -> Dict[str, Any]:
    logger.info("Executing tool plan: intent=%s tools=%s", decision.intent, decision.tools)
    
    results: Dict[str, Any] = {
        "intent": decision.intent,
        "tools_executed": [],
    }

    # Extract business context for DB calls
    conv_id = request.businessContext.get("conversationId")
    tool_access_token = request.businessContext.get("toolAccessToken")
    has_tool_access = isinstance(tool_access_token, str) and bool(tool_access_token.strip())
    context = {
        "role": request.role,
        "conversationId": conv_id,
        "shopId": request.businessContext.get("shopId"),
        "channel": request.businessContext.get("channel"),
        "agentId": request.agent.id,
        "toolAccessToken": tool_access_token,
        "traceId": request.businessContext.get("traceId"),
    }
    personal_tools = {
        "get_customer_profile",
        "get_customer_addresses",
        "get_customer_vouchers",
        "get_promotions",
        "get_loyalty_points",
        "get_order_detail",
        "get_order_status",
        "get_order_tracking",
        "get_customer_orders",
        "get_purchase_history",
        "get_return_requests",
        "get_warranty_status",
    }
    if personal_tools.intersection(decision.tools) and not has_tool_access:
        results["auth_required"] = True

    search_query = request.message
    referenced_product_id = extract_context_product_id(request.businessContext)
    if getattr(decision, "product_name", None):
        search_query = decision.product_name
        logger.info("Overriding product search query with referenced product preview='%s'", truncate_text(search_query, 120))
    
    # 1. Vision Model Analysis
    if "analyze_image" in decision.tools:
        # Find the first image attachment (image_url or presignedUrl)
        image_attachments = [att for att in request.attachments if att.attachmentType == "IMAGE"]
        if image_attachments:
            # Use mediaUrl or check if presignedUrl is available
            img = image_attachments[0]
            # Since presignedUrl is not defined in older ChatAttachment schema but is requested in refactor,
            # we check if hasattr/dict lookup is possible
            img_url = img.mediaUrl
            if not img_url and isinstance(img, dict):
                img_url = img.get("presignedUrl") or img.get("mediaUrl")
            elif not img_url:
                img_url = getattr(img, "presignedUrl", None)

            if img_url:
                results["image_analysis_query"] = analyze_product_image(img_url)
                search_query = results["image_analysis_query"]
                results["tools_executed"].append("analyze_image")
            else:
                logger.warning("analyze_image tool requested but no valid image URL found.")
        else:
            logger.warning("analyze_image tool requested but no image attachment present.")

    # 2. Product Search in Qdrant
    if "product_search" in decision.tools:
        candidates = search_product_candidates(
            search_query,
            limit=request.agent.topK,
            category_name=getattr(decision, "category_name", None),
        )

        # Check for direct image matches if an image is attached
        image_attachments = [att for att in request.attachments if att.attachmentType == "IMAGE"]
        if image_attachments:
            img = image_attachments[0]
            img_filename = getattr(img, "fileName", None)
            if img_filename:
                import os
                matched_candidates = []
                for c in candidates:
                    image_keys = c.get("imageKeys") or []
                    if any(os.path.basename(k).lower() == img_filename.lower() for k in image_keys if k):
                        c["score"] = 1.0
                        matched_candidates.append(c)
                if matched_candidates:
                    logger.info("Direct image match found: file_name=%s candidates=%s", img_filename, len(matched_candidates))
                    candidates = matched_candidates

        results["product_candidates"] = filter_explicit_product_matches(
            search_query,
            candidates,
        )
        logger.info("Product search tool completed: raw_candidates=%s filtered_candidates=%s", len(candidates), len(results["product_candidates"]))
        if not results["product_candidates"]:
            logger.warning("Product search tool found no suitable candidates")
        results["tools_executed"].append("product_search")

    # 3. Product Details Resolution from DB
    if "resolve_product_candidates" in decision.tools or "get_product_detail" in decision.tools or "product_search" in decision.tools:
        candidates = results.get("product_candidates", [])
        if not candidates and "product_search" not in decision.tools:
            # Fallback: search with current query to get candidates
            candidates = filter_explicit_product_matches(
                search_query,
                search_product_candidates(
                    search_query,
                    limit=request.agent.topK,
                    category_name=getattr(decision, "category_name", None),
                ),
            )
            results["product_candidates"] = candidates
        
        product_ids = list(set([c["productId"] for c in candidates if c.get("productId")]))
        variant_ids = list(set([c["variantId"] for c in candidates if c.get("variantId")]))
        
        if product_ids or variant_ids:
            results["resolved_products"] = resolve_products(product_ids, variant_ids, context)
            results["tools_executed"].append("resolve_product_candidates")
        else:
            results["resolved_products"] = []

    # 4. Knowledge Base RAG Search
    if "knowledge_search" in decision.tools:
        results["knowledge_context"] = search_knowledge(
            query=request.message,
            dataset_ids=request.datasetIds,
            limit=request.agent.topK,
            score_threshold=request.agent.scoreThreshold
        )
        logger.info("Knowledge search tool completed: contexts=%s", len(results["knowledge_context"]))
        if not results["knowledge_context"]:
            logger.warning("Knowledge search tool found no suitable context")
        results["tools_executed"].append("knowledge_search")

    # 5. Customer Profile Info
    if "get_customer_profile" in decision.tools and has_tool_access:
        profile = get_customer_profile("", context)
        if profile:
            results["customer_profile"] = profile
            results["tools_executed"].append("get_customer_profile")

    if "get_customer_addresses" in decision.tools and has_tool_access:
        addresses = get_customer_addresses("", context)
        results["customer_addresses"] = addresses
        results["tools_executed"].append("get_customer_addresses")

    # 6. Customer Vouchers / Coupons
    if "get_customer_vouchers" in decision.tools and has_tool_access:
        vouchers = get_customer_vouchers("", context)
        results["customer_vouchers"] = vouchers
        results["tools_executed"].append("get_customer_vouchers")

    if "get_promotions" in decision.tools and has_tool_access:
        promotions = get_promotions("", context)
        results["promotions"] = promotions
        results["tools_executed"].append("get_promotions")

    # 7. Customer Loyalty Points
    if "get_loyalty_points" in decision.tools and has_tool_access:
        points = get_loyalty_points("", context)
        if points:
            results["loyalty_points"] = points
            results["tools_executed"].append("get_loyalty_points")

    # 8. Order Details, Status, Tracking
    order_id_tools = {"get_order_detail", "get_order_status", "get_order_tracking", "get_customer_orders"}
    if order_id_tools.intersection(decision.tools) and has_tool_access:
        # Extract order ID if explicitly asked
        extracted_order_id = extract_identifier(request.message)
        
        # Call resolve_orders
        order_info = resolve_orders(extracted_order_id, context)
        results["order_info"] = order_info
        results["tools_executed"].append("resolve_orders")
        
        if "get_order_tracking" in decision.tools and extracted_order_id:
            tracking = get_order_tracking(extracted_order_id, context)
            results["order_tracking"] = tracking
            results["tools_executed"].append("get_order_tracking")

    if "get_purchase_history" in decision.tools and has_tool_access:
        order_info = get_customer_orders(context)
        results["order_info"] = order_info
        results["tools_executed"].append("get_purchase_history")

    if "get_return_requests" in decision.tools and has_tool_access:
        returns = get_return_requests("", context)
        results["return_requests"] = returns
        results["tools_executed"].append("get_return_requests")

    if "get_product_reviews" in decision.tools:
        product_id_for_reviews = first_resolved_product_id(results) or referenced_product_id
        if product_id_for_reviews:
            reviews = get_product_reviews(product_id_for_reviews, context, size=5)
            results["product_reviews"] = reviews
            results["tools_executed"].append("get_product_reviews")
        else:
            results["product_reviews"] = []

    if "get_sale_products" in decision.tools:
        sale_products = get_sale_products(context, limit=request.agent.topK)
        results["resolved_products"] = sale_products
        results["tools_executed"].append("get_sale_products")

    if "get_catalog_overview" in decision.tools:
        catalog_overview = get_catalog_overview(
            context,
            category_name=getattr(decision, "category_name", None),
            products_per_category=3,
            include_empty=True,
        )
        results["catalog_overview"] = catalog_overview or {}
        if is_category_mapping_question(request.message):
            results["suppress_catalog_recommendations"] = True
        results["tools_executed"].append("get_catalog_overview")

    # 9. Warranty Info
    if "get_warranty_status" in decision.tools:
        item_id = extract_identifier(request.message)
        if item_id:
            warranty = get_warranty_status(item_id, context)
            results["warranty"] = warranty
            results["tools_executed"].append("get_warranty_status")

    logger.info("Completed execution of tool plan: executed=%s", results["tools_executed"])
    return results


def extract_context_product_id(business_context: Dict[str, Any]) -> Optional[str]:
    for key in ("currentProductId", "productId"):
        value = business_context.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    page_context = business_context.get("pageContext")
    if isinstance(page_context, dict):
        for key in ("currentProductId", "productId"):
            value = page_context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def is_category_mapping_question(message: str) -> bool:
    normalized = normalize_text(message)
    return "thuoc danh muc" in normalized or "danh muc nao" in normalized or "danh muc gi" in normalized


def normalize_text(value: str) -> str:
    no_marks = "".join(
        char for char in unicodedata.normalize("NFD", (value or "").lower())
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(no_marks.strip().split())


def first_resolved_product_id(results: Dict[str, Any]) -> Optional[str]:
    for product in results.get("resolved_products", []):
        product_id = str(product.get("productId") or "").strip()
        if product_id:
            return product_id
    return None
