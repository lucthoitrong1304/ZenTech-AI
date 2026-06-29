import json
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import List, Any

from app.config import settings
from app.schemas.agent import AgentRespondRequest
from app.services.openai_client import build_client

logger = logging.getLogger("ai-service")


@dataclass(frozen=True)
class ContextRouteDecision:
    intent: str
    tools: List[str]
    reason: str
    should_search_knowledge: bool = False
    category_name: str | None = None
    product_name: str | None = None


def decide_context_tools(request: AgentRespondRequest) -> ContextRouteDecision:
    message = normalize(request.message)
    if not message:
        return ContextRouteDecision("SMALL_TALK", [], "empty_message")

    # Quick heuristic bypass for common greeting / closing small talk
    if is_simple_small_talk(message):
        return ContextRouteDecision("SMALL_TALK", [], "heuristic_small_talk")

    heuristic = route_common_lookup_intents(message, request)
    if heuristic:
        return heuristic

    # Otherwise, use LLM for robust intent classification and tool planning
    return classify_intent_via_llm(request)


def normalize(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    no_marks = "".join(
        char for char in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(no_marks.strip().split())


def is_simple_small_talk(message: str) -> bool:
    small_talk_phrases = {
        "hi", "hello", "hey", "chao", "xin chao", "alo", "ok", "oke", "okay",
        "cam on", "thanks", "thank you", "bye", "tam biet"
    }
    if message in small_talk_phrases:
        return True
    
    words = message.split()
    greeting_tokens = ("chao", "hello", "hi", "thanks", "cam on")
    return len(words) <= 2 and any(token in message for token in greeting_tokens)


def route_common_lookup_intents(message: str, request: AgentRespondRequest) -> ContextRouteDecision | None:
    has_product_context = bool(
        request.businessContext.get("currentProductId")
        or (
            isinstance(request.businessContext.get("pageContext"), dict)
            and request.businessContext["pageContext"].get("currentProductId")
        )
    )

    if any(token in message for token in ("don hang", "order", "lich su mua", "mua hang")):
        return ContextRouteDecision(
            "ORDER_QA",
            ["get_customer_orders", "get_order_detail", "get_order_status"],
            "heuristic_order_lookup",
        )

    if any(token in message for token in ("voucher", "ma giam", "khuyen mai", "coupon")):
        return ContextRouteDecision(
            "PROMOTION_QA",
            ["get_customer_vouchers", "get_promotions"],
            "heuristic_promotion_lookup",
        )

    review_tokens = ("danh gia", "review", "nhan xet", "binh luan", "tich cuc", "tieu cuc", "sao")
    reference_tokens = ("san pham nay", "san pham tren", "sp nay", "sp tren", "cai nay", "con nay", "no")
    if any(token in message for token in review_tokens):
        tools = ["get_product_reviews"]
        if not has_product_context and not any(token in message for token in reference_tokens):
            tools = ["product_search", "resolve_product_candidates", "get_product_reviews"]
        return ContextRouteDecision(
            "PRODUCT_QA",
            tools,
            "heuristic_product_review_lookup",
        )

    return None
INTENT_ROUTING_PROMPT = """Bạn là Router phân loại ý định (Intent Router) cho hệ thống trợ lý ảo ZenTech.
Nhiệm vụ của bạn là đọc tin nhắn của khách hàng, lịch sử hội thoại và thông tin đính kèm để phân loại ý định của khách hàng vào một trong các nhóm sau, đồng thời lập Tool Plan phù hợp:

Các ý định (Intent) hợp lệ và các Tool tương ứng có thể chọn:
1. `SMALL_TALK`: Giao tiếp thông thường (chào hỏi, cảm ơn, hỏi han linh tinh không liên quan nghiệp vụ).
   - Tool phù hợp: [] (Không dùng tool).
2. `KNOWLEDGE_QA`: Hỏi về chính sách bán hàng chung, hướng dẫn, FAQ, bảo hành chung, vận chuyển, đổi trả chung.
   - Tool phù hợp: ["knowledge_search"].
3. `PRODUCT_QA`: Hỏi thông tin, tư vấn sản phẩm, danh sách sản phẩm cửa hàng đang kinh doanh (ví dụ: "bên bạn có những sản phẩm nào", "toàn bộ sản phẩm đang kinh doanh", "cửa hàng bán gì"), giá cả, tồn kho, đánh giá của sản phẩm bằng text.
   - Tool phù hợp: ["product_search", "resolve_product_candidates", "get_product_detail", "get_product_stock", "get_product_reviews"].
4. `IMAGE_PRODUCT_QA`: Khách hàng gửi ảnh sản phẩm và hỏi thông tin về sản phẩm đó (khi attachments có chứa hình ảnh).
   - Tool phù hợp: ["analyze_image", "product_search", "resolve_product_candidates", "get_product_detail"].
5. `PRODUCT_AND_POLICY_QA`: Hỏi sản phẩm đồng thời hỏi chính sách (ví dụ: "Sản phẩm A có bảo hành thế nào?").
   - Tool phù hợp: ["product_search", "resolve_product_candidates", "get_product_detail", "knowledge_search"].
6. `ORDER_QA`: Hỏi trạng thái đơn hàng, tra cứu mã đơn hàng, theo dõi giao hàng.
   - Tool phù hợp: ["get_customer_orders", "get_order_detail", "get_order_status", "get_order_tracking"].
7. `ORDER_AND_POLICY_QA`: Hỏi đơn hàng kèm chính sách đổi trả/hoàn tiền liên quan đến đơn hàng đó.
   - Tool phù hợp: ["get_order_detail", "get_order_status", "knowledge_search"].
8. `CUSTOMER_ACCOUNT_QA`: Hỏi thông tin tài khoản cá nhân, lịch sử mua hàng, điểm tích lũy của mình.
   - Tool phù hợp: ["get_customer_profile", "get_loyalty_points", "get_purchase_history"].
9. `PROMOTION_QA`: Hỏi về voucher, khuyến mãi hiện hành của store hoặc voucher cá nhân của khách.
   - Tool phù hợp: ["get_customer_vouchers", "get_promotions"].
10. `WARRANTY_QA`: Hỏi về tình trạng bảo hành cụ thể của sản phẩm đã mua.
    - Tool phù hợp: ["get_warranty_status"].
11. `BUSINESS_DATA_QA`: Hỏi thông tin nghiệp vụ khác cần DB tools (ví dụ: thông tin cửa hàng, địa chỉ, giờ mở cửa).
    - Tool phù hợp: ["get_store_info"].
12. `HUMAN_HANDOFF`: Yêu cầu gặp nhân viên hoặc khi AI không thể giải quyết.
    - Tool phù hợp: [] (Không dùng tool).

Quy tắc quan trọng:
- Nếu tin nhắn chứa tệp đính kèm là hình ảnh (hoặc người dùng đề cập đến ảnh đính kèm), ưu tiên chọn `IMAGE_PRODUCT_QA` và dùng tool `analyze_image`.
- Nếu khách hàng hỏi về các sản phẩm thuộc một danh mục cụ thể (ví dụ: "chargers", "sạc", "bàn phím", "keyboards", "loa", "tai nghe"), hãy trích xuất tên danh mục đó vào trường `category_name`.
- Nếu tin nhắn của khách hàng sử dụng các từ mang tính chất tham chiếu/thay thế (ví dụ: "sản phẩm đó", "nó", "con này", "cái này", "chi tiết sản phẩm đi", "còn hàng không") để hỏi tiếp về sản phẩm đã được nhắc đến ở lượt thoại ngay trước đó trong lịch sử hội thoại (lượt trả lời của trợ lý ảo), hãy tìm tên chính xác của sản phẩm đó từ lịch sử và trích xuất vào trường `product_name`.
- Trả về kết quả dưới dạng JSON duy nhất có cấu trúc:
{
  "intent": "TÊN_INTENT",
  "tools": ["tool_1", "tool_2"],
  "reason": "Lý do ngắn gọn phân loại",
  "category_name": "Tên danh mục được trích xuất (nếu có, ví dụ: 'chargers' hoặc 'keyboards'), ngược lại là null",
  "product_name": "Tên sản phẩm được trích xuất hoặc tham chiếu từ lịch sử chat (nếu có, ví dụ: 'Power Strip'), ngược lại là null"
}
"""

def classify_intent_via_llm(request: AgentRespondRequest) -> ContextRouteDecision:
    history_str = ""
    for h in request.history[-5:]:
        history_str += f"{h.role}: {h.content}\n"

    attachment_info = []
    for att in request.attachments:
        attachment_info.append({
            "fileName": att.fileName,
            "attachmentType": att.attachmentType,
            "contentType": att.contentType
        })

    user_context = (
        f"Lịch sử chat gần đây:\n{history_str}\n"
        f"Tin nhắn hiện tại: {request.message}\n"
        f"Tệp đính kèm: {json.dumps(attachment_info, ensure_ascii=False)}\n"
    )

    messages = [
        {"role": "system", "content": INTENT_ROUTING_PROMPT},
        {"role": "user", "content": user_context}
    ]

    try:
        client = build_client()
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.chat_deployment_name,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content.strip()
        else:
            response = build_client().responses.create(
                model=settings.chat_deployment_name,
                input=messages,
            )
            raw_content = response.output_text.strip()

        # Parse JSON output safely
        # Strip markdown code blocks if any
        if raw_content.startswith("```"):
            lines = raw_content.splitlines()
            if lines[0].startswith("```json"):
                raw_content = "\n".join(lines[1:-1])
            else:
                raw_content = "\n".join(lines[1:-1])

        data = json.loads(raw_content)
        intent = data.get("intent", "KNOWLEDGE_QA")
        tools = data.get("tools", [])
        reason = data.get("reason", "")
        category_name = data.get("category_name")
        product_name = data.get("product_name")
        
        should_search_knowledge = "knowledge_search" in tools
        logger.info(f"Intent classified: {intent} | Tools: {tools} | Reason: {reason} | Category: {category_name} | Product: {product_name}")
        return ContextRouteDecision(intent, tools, reason, should_search_knowledge, category_name, product_name)

    except Exception as ex:
        logger.error(f"Failed to classify intent via LLM, fallback to KNOWLEDGE_QA: {str(ex)}")
        # Default fallback
        return ContextRouteDecision("KNOWLEDGE_QA", ["knowledge_search"], f"fallback_error: {str(ex)}", True)
