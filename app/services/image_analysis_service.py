import logging
from app.config import settings
from app.services.openai_client import build_client

logger = logging.getLogger("ai-service")


def analyze_product_image(image_url: str) -> str:
    """
    Calls the Vision model (Azure OpenAI) to analyze the product image
    and return a text-based search query in Vietnamese.
    """
    logger.info(f"Analyzing product image via vision model: {image_url}")

    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là chuyên gia phân tích hình ảnh sản phẩm công nghệ và phụ kiện của ZenTech. "
                "Nhiệm vụ của bạn là nhận diện sản phẩm trong ảnh và đưa ra câu truy vấn tìm kiếm ngắn gọn (search query) bằng tiếng Việt. "
                "Hãy tập trung nhận diện tên gọi phổ biến của sản phẩm (ví dụ: củ sạc Alpha65, đế sạc Power Strip, bàn phím cơ Mercury, loa Bluetooth, tai nghe) kèm theo thương hiệu (GravaStar) và phong cách nổi bật (cơ khí, mecha, robot, cyberpunk) nếu có. "
                "Tránh viết mô tả dài dòng chi tiết về các bộ phận hoặc chất liệu nhựa/kim loại. "
                "Đầu ra CHỈ trả về duy nhất một chuỗi từ khóa tìm kiếm ngắn gọn, không thêm lời giải thích, không thêm dấu nháy hay văn bản dư thừa khác."
            )
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Phân tích sản phẩm trong ảnh này và trả về câu truy vấn tìm kiếm bằng tiếng Việt."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            ]
        }
    ]

    try:
        client = build_client()
        model_name = settings.azure_openai_vision_model_name or "gpt-5.4-mini"

        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2,
                max_completion_tokens=150
            )
            description = response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=model_name,
                input=messages,
            )
            description = response.output_text.strip()

        logger.info(f"Vision analysis completed. Search query generated: {description}")
        return description

    except Exception as ex:
        logger.error(f"Failed to analyze product image via vision model: {str(ex)}")
        return "sản phẩm trong hình ảnh"
