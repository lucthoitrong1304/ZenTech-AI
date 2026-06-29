import json
import logging

from app.config import settings
from app.prompts.inventory_management_prompt import SYSTEM_PROMPT_INVENTORY
from app.schemas.inventory_management import InventoryRecommendRequest
from app.services.openai_client import build_client

logger = logging.getLogger("ai-service.management")
llm_logger = logging.getLogger("ai-service.llm")


def generate_inventory_recommendation(request: InventoryRecommendRequest) -> str:
    logger.info("Received inventory recommendation request: item_count=%s", len(request.items))
    items_data = [
        {
            "product_name": item.productName,
            "variant_name": item.variantName,
            "current_stock": item.currentStock,
            "weekly_sales_velocity": item.averageWeeklySales,
            "system_suggested_qty": item.suggestedQty,
        }
        for item in request.items
    ]

    formatted_items = json.dumps(items_data, indent=2, ensure_ascii=False)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_INVENTORY},
        {
            "role": "user",
            "content": f"Dưới đây là danh sách sản phẩm tồn kho thấp cần phân tích:\n\n{formatted_items}",
        },
    ]

    try:
        client = build_client()
        llm_logger.info("Starting LLM call for inventory recommendation: model=%s item_count=%s", settings.azure_openai_model_name, len(request.items))
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.azure_openai_model_name,
                messages=messages,
                temperature=0.3,
            )
            content = response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=settings.azure_openai_model_name,
                input=messages,
            )
            content = response.output_text.strip()
        llm_logger.info("LLM call completed for inventory recommendation: response_length=%s", len(content))
        logger.info("Inventory recommendation completed: item_count=%s", len(request.items))
        return content
    except Exception:
        logger.error("Failed to generate inventory recommendation", exc_info=True)
        raise
