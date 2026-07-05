import json
import logging
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_utils import truncate_text

logger = logging.getLogger("ai-service.tool-orchestrator")


def _get_headers(context: Dict[str, Any]) -> Optional[Dict[str, str]]:
    token = str(context.get("toolAccessToken") or "").strip()
    if not token:
        logger.warning("AI tool access token is missing; backend tool call skipped.")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    trace_id = str(context.get("traceId") or "").strip()
    if trace_id:
        headers["X-Trace-Id"] = trace_id
    return headers


def _make_request(url: str, method: str, context: Dict[str, Any], payload: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    headers = _get_headers(context)
    if headers is None:
        return None

    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data_bytes,
        headers=headers,
        method=method
    )

    try:
        logger.info("Calling backend AI tool API: method=%s url=%s", method, url)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                raw_data = response.read().decode("utf-8")
                # Parse ApiResponse format from Spring Boot
                json_data = json.loads(raw_data)
                if isinstance(json_data, dict) and "data" in json_data:
                    return json_data["data"]
                return json_data
            else:
                logger.error("Backend AI tool API returned error status: status=%s", response.status)
                return None
    except urllib.error.HTTPError as ex:
        try:
            err_body = ex.read().decode("utf-8")
            logger.error("HTTP error calling backend AI tool API: status=%s body_preview='%s'", ex.code, truncate_text(err_body, 200), exc_info=True)
        except Exception:
            logger.error("HTTP error calling backend AI tool API: status=%s reason=%s", ex.code, ex.reason, exc_info=True)
        return None
    except Exception as ex:
        logger.error("Failed to call backend AI tool API", exc_info=True)
        return None


def resolve_products(product_ids: List[str], variant_ids: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/products/resolve"
    payload = {
        "productIds": product_ids,
        "variantIds": variant_ids,
    }
    result = _make_request(url, "POST", context, payload)
    return result if isinstance(result, list) else []


def resolve_orders(order_id: Optional[str], context: Dict[str, Any]) -> Optional[Any]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/orders/resolve"
    payload = {
        "orderId": order_id,
    }
    return _make_request(url, "POST", context, payload)


def get_customer_orders(context: Dict[str, Any]) -> Optional[Any]:
    return resolve_orders(None, context)


def get_product_reviews(product_id: str, context: Dict[str, Any], page: int = 0, size: int = 5) -> List[Dict[str, Any]]:
    query = {
        "page": max(page, 0),
        "size": min(max(size, 1), 10),
    }
    query_str = urllib.parse.urlencode(query)
    url = f"{settings.spring_boot_api_url}/api/ai/tools/products/{product_id}/reviews?{query_str}"
    result = _make_request(url, "GET", context)
    return result if isinstance(result, list) else []


def get_customer_profile(user_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/customers/me/profile"
    return _make_request(url, "GET", context)


def get_customer_addresses(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/customers/me/addresses"
    result = _make_request(url, "GET", context)
    return result if isinstance(result, list) else []


def get_customer_vouchers(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/customers/me/vouchers"
    result = _make_request(url, "GET", context)
    return result if isinstance(result, list) else []


def get_promotions(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_customer_vouchers(user_id, context)


def get_loyalty_points(user_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/customers/me/loyalty-points"
    return _make_request(url, "GET", context)


def get_order_tracking(order_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/orders/{order_id}/tracking"
    return _make_request(url, "GET", context)


def get_return_requests(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/customers/me/returns"
    result = _make_request(url, "GET", context)
    return result if isinstance(result, list) else []


def get_warranty_status(order_item_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_api_url}/api/ai/tools/warranties/{order_item_id}"
    return _make_request(url, "GET", context)
