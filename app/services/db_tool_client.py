import json
import logging
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger("ai-service")


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
        logger.info(f"Calling internal API: {method} {url}")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                raw_data = response.read().decode("utf-8")
                # Parse ApiResponse format from Spring Boot
                json_data = json.loads(raw_data)
                if isinstance(json_data, dict) and "data" in json_data:
                    return json_data["data"]
                return json_data
            else:
                logger.error(f"Internal API returned status code {response.status}")
                return None
    except urllib.error.HTTPError as ex:
        try:
            err_body = ex.read().decode("utf-8")
            logger.error(f"HTTP Error calling internal API: {ex.code} - {err_body}")
        except Exception:
            logger.error(f"HTTP Error calling internal API: {ex.code} - {ex.reason}")
        return None
    except Exception as ex:
        logger.error(f"Failed to call internal API: {str(ex)}")
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


def get_customer_orders(context: Dict[str, Any]) -> Optional[Any]:
    return resolve_orders(None, context)


def get_product_reviews(product_id: str, context: Dict[str, Any], page: int = 0, size: int = 5) -> List[Dict[str, Any]]:
    query = {
        "page": max(page, 0),
        "size": min(max(size, 1), 10),
    }
    query_str = urllib.parse.urlencode(query)
    url = f"{settings.spring_boot_internal_url}/internal/ai/products/{product_id}/reviews?{query_str}"
    result = _make_request(url, "GET")
    return result if isinstance(result, list) else []


def get_customer_profile(user_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/customers/{user_id}/profile"
    # Convert GET params from context
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    return _make_request(full_url, "GET")


def get_customer_addresses(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/customers/{user_id}/addresses"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    result = _make_request(full_url, "GET")
    return result if isinstance(result, list) else []


def get_customer_vouchers(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/customers/{user_id}/vouchers"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    result = _make_request(full_url, "GET")
    return result if isinstance(result, list) else []


def get_promotions(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_customer_vouchers(user_id, context)


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


def get_return_requests(user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/customers/{user_id}/returns"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    result = _make_request(full_url, "GET")
    return result if isinstance(result, list) else []


def get_warranty_status(order_item_id: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.spring_boot_internal_url}/internal/ai/warranties/{order_item_id}"
    query_str = urllib.parse.urlencode({k: str(v) for k, v in context.items() if v is not None})
    full_url = f"{url}?{query_str}" if query_str else url
    return _make_request(full_url, "GET")
