import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_utils import truncate_text

logger = logging.getLogger("ai-service.tool-orchestrator")


def _get_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Internal-Token": settings.spring_boot_internal_token,
    }


def _make_request(url: str, method: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    headers = _get_headers()
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
        logger.info("Calling internal API: method=%s url=%s", method, url)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                raw_data = response.read().decode("utf-8")
                # Parse ApiResponse format from Spring Boot
                json_data = json.loads(raw_data)
                if isinstance(json_data, dict) and "data" in json_data:
                    return json_data["data"]
                return json_data
            else:
                logger.error("Internal API returned error status: status=%s", response.status)
                return None
    except urllib.error.HTTPError as ex:
        try:
            err_body = ex.read().decode("utf-8")
            logger.error("HTTP error calling internal API: status=%s body_preview='%s'", ex.code, truncate_text(err_body, 200), exc_info=True)
        except Exception:
            logger.error("HTTP error calling internal API: status=%s reason=%s", ex.code, ex.reason, exc_info=True)
        return None
    except Exception as ex:
        logger.error("Failed to call internal API", exc_info=True)
        return None


def resolve_products(product_ids: List[str], variant_ids: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/products/resolve"
    payload = {
        "productIds": product_ids,
        "variantIds": variant_ids,
        "context": context
    }
    result = _make_request(url, "POST", payload)
    return result if isinstance(result, list) else []


def resolve_orders(order_id: Optional[str], context: Dict[str, Any]) -> Optional[Any]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/orders/resolve"
    payload = {
        "orderId": order_id,
        "context": context
    }
    return _make_request(url, "POST", payload)


def get_customer_profile(user_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/customers/{user_id}/profile"
    # Convert GET params from context
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    return _make_request(full_url, "GET")


def get_customer_vouchers(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/customers/{user_id}/vouchers"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    result = _make_request(full_url, "GET")
    return result if isinstance(result, list) else []


def get_loyalty_points(user_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/customers/{user_id}/loyalty-points"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    return _make_request(full_url, "GET")


def get_order_tracking(order_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/orders/{order_id}/tracking"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    return _make_request(full_url, "GET")


def get_warranty_status(order_item_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/warranties/{order_item_id}"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    return _make_request(full_url, "GET")
