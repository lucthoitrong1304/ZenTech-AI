import json
from typing import Any, Dict, List

from app.schemas.agent import AgentRespondRequest
from app.utils.chat_roles import to_openai_role

MAX_HISTORY_MESSAGES = 10
MAX_ANALYZABLE_ATTACHMENTS = 3
MAX_TOTAL_FILE_TEXT_CHARS = 12_000


def build_agent_model_input(
    request: AgentRespondRequest,
    orchestrator_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    # 1. Base System Instruction
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": build_runtime_instruction(request),
        }
    ]

    # 2. Guardrails
    if request.agent.guardrails:
        messages.append({"role": "system", "content": f"HƯỚNG DẪN HÀNH VI (GUARDRAILS):\n{request.agent.guardrails.strip()}"})

    # Strict Hallucination Guardrails & Technical Non-Disclosure
    messages.append({
        "role": "system",
        "content": (
            "QUY TẮC PHÒNG CHỐNG BỊA ĐẶT VÀ BẢO MẬT THÔNG TIN HỆ THỐNG:\n"
            "- Tuyệt đối không được tự bịa ra thông tin về: giá sản phẩm, tồn kho, khuyến mãi, đánh giá sản phẩm, mã đơn hàng, trạng thái giao hàng, voucher cá nhân, điểm tích lũy hoặc thông tin bảo hành.\n"
            "- Mọi thông tin nghiệp vụ trên bắt buộc phải lấy từ phần dữ liệu thực tế được cung cấp dưới đây.\n"
            "- Nếu phần dữ liệu dưới đây không có hoặc rỗng, hãy trả lời lịch sự rằng hệ thống chưa tìm thấy thông tin này trong cơ sở dữ liệu của ZenTech thay vì tự suy đoán hoặc đoán mò.\n"
            "- Đối với thông tin chính sách chung (đổi trả, bảo hành chung, vận chuyển), hãy dựa hoàn toàn vào Context tri thức được cung cấp. Không tự ý nghĩ ra chính sách.\n"
            "- Khi hệ thống cung cấp danh sách sản phẩm ở mục 'THÔNG TIN SẢN PHẨM THỰC TẾ TỪ DATABASE', hãy liệt kê và giới thiệu ĐẦY ĐỦ tất cả các sản phẩm này đến khách hàng mà không tự ý lọc bỏ hay đánh giá chủ quan sản phẩm nào không thuộc danh mục (vì toàn bộ danh sách này đã được hệ thống truy vấn và xác định chính xác từ database trước đó).\n"
            "- QUY TẮC BẢO MẬT THÔNG TIN HỆ THỐNG VÀ TRẢ LỜI KHÁCH HÀNG: Tuyệt đối KHÔNG tiết lộ, đề cập hoặc sử dụng các thông tin kỹ thuật nội bộ của hệ thống với khách hàng, bao gồm: kết quả nhận diện của AI Vision (ví dụ: 'đế sạc GravaStar mecha robot'), điểm số tìm kiếm (Score), độ tin cậy tìm kiếm ('Thấp', 'Trung bình', 'Cao'), hoặc các cụm từ kỹ thuật như 'hệ thống nhận diện', 'truy vấn database'. Trả lời một cách tự nhiên, trực tiếp và thân thiện dưới vai trò một nhân viên tư vấn bán hàng của ZenTech đang trò chuyện với khách."
        )
    })

    # 3. Business Context (UserId, Role, etc.)
    business_context = build_business_context_message(request.businessContext)
    if business_context:
        messages.append({"role": "system", "content": business_context})

    # 4. Image Analysis result
    image_query = orchestrator_results.get("image_analysis_query")
    if image_query:
        messages.append({
            "role": "system",
            "content": f"KẾT QUẢ PHÂN TÍCH ẢNH GỬI ĐẾN:\nKhách hàng đã gửi một hình ảnh sản phẩm. Hệ thống AI Vision nhận diện sản phẩm này là: \"{image_query}\"."
        })

    # 5. Resolved Products Context from DB
    resolved_products = orchestrator_results.get("resolved_products")
    if resolved_products:
        messages.append({
            "role": "system",
            "content": build_resolved_products_message(resolved_products, orchestrator_results.get("product_candidates", []))
        })
    elif "product_search" in orchestrator_results.get("tools_executed", []):
        messages.append({
            "role": "system",
            "content": "KẾT QUẢ TRA CỨU SẢN PHẨM: Không tìm thấy sản phẩm nào khớp trong cơ sở dữ liệu."
        })

    # 6. Business DB Tool Results (Orders, Vouchers, Points, Warranty)
    db_context = build_db_tool_context_message(orchestrator_results)
    if db_context:
        messages.append({"role": "system", "content": db_context})

    # 7. RAG Knowledge Context
    knowledge_context = orchestrator_results.get("knowledge_context")
    if knowledge_context:
        messages.append({
            "role": "system",
            "content": build_knowledge_context_message(knowledge_context)
        })

    # 8. Chat History
    for item in request.history[-MAX_HISTORY_MESSAGES:]:
        content = item.content.strip()
        if content:
            messages.append({"role": to_openai_role(item.role), "content": content})

    # 9. User message
    messages.append({"role": "user", "content": build_user_content(request)})
    return messages


def build_user_content(request: AgentRespondRequest) -> str | List[Dict[str, Any]]:
    content_parts: List[Dict[str, Any]] = [
        {"type": "text", "text": request.message.strip()}
    ]

    for attachment in request.attachments[:MAX_ANALYZABLE_ATTACHMENTS]:
        # Handle images
        if attachment.attachmentType == "IMAGE":
            img_url = attachment.mediaUrl
            if not img_url and isinstance(attachment, dict):
                img_url = attachment.get("presignedUrl") or attachment.get("mediaUrl")
            elif not img_url:
                img_url = getattr(attachment, "presignedUrl", None)

            if img_url:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": img_url
                    }
                })

    if len(content_parts) == 1:
        return content_parts[0]["text"]
    return content_parts


def build_business_context_message(context: Dict[str, Any]) -> str | None:
    if not context:
        return None

    lines = [f"- {key}: {value}" for key, value in context.items() if value is not None]
    if not lines:
        return None
    return "NGỮ CẢNH HỆ THỐNG / THÔNG TIN PHIÊN CHAT:\n" + "\n".join(lines)


def build_runtime_instruction(request: AgentRespondRequest) -> str:
    return (
        request.agent.systemPrompt.strip()
        + "\n\n"
        + "Trả lời tự nhiên theo system prompt, vai trò và lịch sử hội thoại. "
        + "Không mở rộng phạm vi ngoài system prompt hoặc guardrails của agent. "
        + "Nếu thông tin nghiệp vụ (giá cả, tồn kho, đơn hàng) được cung cấp từ cơ sở dữ liệu bên dưới, hãy dùng nó để trả lời chính xác. "
        + "Nếu không tìm thấy thông tin phù hợp, hãy từ chối lịch sự và đề nghị hỗ trợ chuyển nhân viên nếu cần thiết."
    )


def build_resolved_products_message(resolved: List[Dict[str, Any]], candidates: List[Dict[str, Any]]) -> str:
    # Map candidates score
    scores = {c["variantId"] or c["productId"]: c["score"] for c in candidates}
    
    lines = ["THÔNG TIN SẢN PHẨM THỰC TẾ TỪ DATABASE (SOURCE OF TRUTH):"]
    lines.append("LƯU Ý QUAN TRỌNG: Đây là toàn bộ danh sách sản phẩm khớp với yêu cầu của người dùng được truy vấn từ database của hệ thống. Bạn KHÔNG ĐƯỢC TỰ Ý LỌC BỎ bất kỳ sản phẩm nào dưới đây ra khỏi câu trả lời của mình (phải giới thiệu đầy đủ toàn bộ các sản phẩm này).")
    for idx, prod in enumerate(resolved, 1):
        key = prod.get("variantId") or prod.get("productId")
        score = scores.get(key, 1.0)
        
        # Determine confidence label based on score
        confidence = "Rất cao" if score >= 0.75 else ("Trung bình" if score >= 0.45 else "Thấp (Cần hỏi lại khách hàng để xác nhận)")
        
        variant_desc = f" (Biến thể: {prod.get('variantName')})" if prod.get("variantName") else ""
        lines.append(
            f"{idx}. {prod.get('name')}{variant_desc}\n"
            f"   - ProductId: {prod.get('productId')}\n"
            f"   - VariantId: {prod.get('variantId')}\n"
            f"   - Sku: {prod.get('sku')}\n"
            f"   - Giá thực tế: {prod.get('price'):,.0f} VND\n"
            f"   - Tồn kho: {prod.get('stock')} sản phẩm\n"
            f"   - Khuyến mãi: {prod.get('promotionInfo') or 'Không có'}\n"
            f"   - Đánh giá: {prod.get('rating') or 'Chưa có'} sao ({prod.get('reviewCount') or 0} đánh giá)\n"
            f"   - Độ tin cậy tìm kiếm: {confidence} (Score={score:.3f})"
        )
        detail_sections = [
            ("MÔ TẢ CHI TIẾT", prod.get("description")),
            ("THÔNG SỐ KỸ THUẬT", prod.get("specifications")),
            ("TƯƠNG THÍCH", prod.get("compatibility")),
            ("BỘ SẢN PHẨM", prod.get("boxContents")),
            ("HỖ TRỢ", prod.get("supportInfo")),
            ("SẢN PHẨM LIÊN QUAN VÀ TƯƠNG TỰ", prod.get("relatedProducts")),
        ]
        for title, content in detail_sections:
            if content and str(content).strip():
                lines.append(f"   - {title} (Markdown):\n{str(content).strip()}")
    return "\n".join(lines)


def build_db_tool_context_message(results: Dict[str, Any]) -> str | None:
    lines = []
    
    # Customer profile
    profile = results.get("customer_profile")
    if profile:
        lines.append(f"THÔNG TIN KHÁCH HÀNG:\n{json.dumps(profile, ensure_ascii=False, indent=2)}")
        
    # Loyalty points
    points = results.get("loyalty_points")
    if points:
        lines.append(f"THÔNG TIN ĐIỂM TÍCH LŨY:\n{json.dumps(points, ensure_ascii=False, indent=2)}")

    # Vouchers
    vouchers = results.get("customer_vouchers")
    if vouchers:
        lines.append(f"DANH SÁCH VOUCHER KHẢ DỤNG:\n{json.dumps(vouchers, ensure_ascii=False, indent=2)}")

    # Orders info
    order = results.get("order_info")
    if order:
        lines.append(f"THÔNG TIN ĐƠN HÀNG TRA CỨU:\n{json.dumps(order, ensure_ascii=False, indent=2)}")

    # Order tracking
    tracking = results.get("order_tracking")
    if tracking:
        lines.append(f"LỘ TRÌNH VẬN CHUYỂN ĐƠN HÀNG:\n{json.dumps(tracking, ensure_ascii=False, indent=2)}")

    # Warranty
    warranty = results.get("warranty")
    if warranty:
        lines.append(f"THÔNG TIN BẢO HÀNH SẢN PHẨM:\n{json.dumps(warranty, ensure_ascii=False, indent=2)}")

    if not lines:
        return None
    
    return "THÔNG TIN NGHIỆP VỤ TỪ DATABASE TRUY XUẤT QUA API NỘI BỘ:\n\n" + "\n\n".join(lines)


def build_knowledge_context_message(context: List[Any]) -> str | None:
    lines = []
    for item in context:
        content = item.content.strip()
        if content:
            lines.append(f"- Nguồn: {item.source or 'dataset'} (Score={item.score:.3f}): {content}")
            
    if not lines:
        return None

    return (
        "NGỮ CẢNH TRI THỨC (CHÍNH SÁCH / FAQ / HƯỚNG DẪN):\n"
        "Hãy dựa hoàn toàn vào thông tin dưới đây để trả lời các câu hỏi chính sách/thủ tục:\n"
        + "\n".join(lines)
    )
