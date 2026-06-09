import json
from app.config import settings
from app.prompts.inventory_management_prompt import SYSTEM_PROMPT_INVENTORY
from app.schemas.inventory_management import InventoryRecommendRequest
from app.services.openai_client import build_client

def generate_inventory_recommendation(request: InventoryRecommendRequest) -> str:
    # Format request data to JSON string for prompt context
    items_data = [
        {
            "product_name": item.productName,
            "variant_name": item.variantName,
            "current_stock": item.currentStock,
            "weekly_sales_velocity": item.averageWeeklySales,
            "system_suggested_qty": item.suggestedQty
        }
        for item in request.items
    ]
    
    formatted_items = json.dumps(items_data, indent=2, ensure_ascii=False)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_INVENTORY},
        {
            "role": "user",
            "content": f"Dưới đây là danh sách sản phẩm tồn kho thấp cần phân tích:\n\n{formatted_items}"
        }
    ]
    
    try:
        client = build_client()
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.azure_openai_model_name,
                messages=messages,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=settings.azure_openai_model_name,
                input=messages,
            )
            return response.output_text.strip()
    except Exception as e:
        raise e
