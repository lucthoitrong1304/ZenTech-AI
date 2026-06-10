from typing import Any

from app.schemas.agent import AgentRespondRequest
from app.schemas.rag import QdrantSearchResult
from app.utils.chat_roles import to_openai_role
from app.utils.document_text import extract_text

MAX_HISTORY_MESSAGES = 10
MAX_ANALYZABLE_ATTACHMENTS = 3
MAX_TOTAL_FILE_TEXT_CHARS = 12_000


def build_agent_model_input(
    request: AgentRespondRequest,
    retrieved_context: list[QdrantSearchResult],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_runtime_instruction(request),
        }
    ]

    if request.agent.guardrails:
        messages.append({"role": "system", "content": request.agent.guardrails.strip()})

    business_context = build_business_context_message(request.businessContext)
    if business_context:
        messages.append({"role": "system", "content": business_context})

    context_message = build_retrieved_context_message(request, retrieved_context)
    if context_message:
        messages.append({"role": "system", "content": context_message})

    for item in request.history[-MAX_HISTORY_MESSAGES:]:
        content = item.content.strip()
        if content:
            messages.append({"role": to_openai_role(item.role), "content": content})

    messages.append({"role": "user", "content": build_user_content(request)})
    return messages


def build_user_content(request: AgentRespondRequest) -> str | list[dict[str, str]]:
    content_parts: list[dict[str, str]] = [
        {"type": "input_text", "text": build_user_text(request)}
    ]

    for attachment in request.attachments[:MAX_ANALYZABLE_ATTACHMENTS]:
        if attachment.attachmentType == "IMAGE" and attachment.mediaUrl:
            content_parts.append({"type": "input_image", "image_url": attachment.mediaUrl})

    if len(content_parts) == 1:
        return content_parts[0]["text"]
    return content_parts


def build_user_text(request: AgentRespondRequest) -> str:
    sections = [request.message.strip()]
    file_context = build_file_context(request)
    if file_context:
        sections.append(file_context)
    return "\n\n".join(section for section in sections if section.strip())


def build_file_context(request: AgentRespondRequest) -> str | None:
    remaining_chars = MAX_TOTAL_FILE_TEXT_CHARS
    file_sections: list[str] = []

    for attachment in request.attachments[:MAX_ANALYZABLE_ATTACHMENTS]:
        if attachment.attachmentType != "FILE" or not attachment.contentBase64:
            continue

        try:
            extracted = extract_text(
                attachment.contentBase64,
                attachment.contentType,
                attachment.fileName,
            ).strip()
        except Exception:
            file_sections.append(
                f"[{attachment.fileName}] Không thể đọc nội dung file này."
            )
            continue

        if not extracted:
            file_sections.append(f"[{attachment.fileName}] File không có nội dung văn bản đọc được.")
            continue

        clipped = extracted[:remaining_chars]
        remaining_chars -= len(clipped)
        file_sections.append(f"[{attachment.fileName}]\n{clipped}")
        if remaining_chars <= 0:
            break

    if not file_sections:
        return None

    return (
        "Nội dung file khách hàng gửi để tham khảo khi trả lời:\n"
        + "\n\n".join(file_sections)
    )


def build_business_context_message(context: dict[str, object]) -> str | None:
    if not context:
        return None

    lines = [f"- {key}: {value}" for key, value in context.items() if value is not None]
    if not lines:
        return None
    return "Ngữ cảnh hệ thống/kinh doanh hiện tại:\n" + "\n".join(lines)


def build_runtime_instruction(request: AgentRespondRequest) -> str:
    return (
        request.agent.systemPrompt.strip()
        + "\n\n"
        + "Trả lời tự nhiên theo system prompt, vai trò và lịch sử hội thoại. "
        + "Không mở rộng phạm vi ngoài system prompt hoặc guardrails của agent. "
        + "Dataset/Qdrant chỉ là nguồn tham khảo bổ sung khi có liên quan và đủ tin cậy. "
        + "Nếu không có retrieved context phù hợp, agent vẫn có thể chào hỏi, tự giới thiệu "
        + "hoặc hỏi thêm thông tin, nhưng không được tự suy đoán kiến thức, định nghĩa hay "
        + "tư vấn ngoài phạm vi được cấu hình. Nếu câu hỏi nằm ngoài phạm vi hỗ trợ, hãy "
        + "từ chối lịch sự theo system prompt và gợi ý người dùng cung cấp thêm thông tin "
        + "liên quan đến ZenTech."
    )


def build_retrieved_context_message(
    request: AgentRespondRequest,
    context: list[QdrantSearchResult],
) -> str | None:
    if not context:
        return None

    lines = [
        f"- Source: {item.source or 'dataset'}, score={item.score:.3f}: {item.content.strip()}"
        for item in context
        if item.content.strip()
    ]
    if not lines:
        return None

    return (
        "Ngữ cảnh từ dataset của agent. Chỉ sử dụng các đoạn dưới đây khi chúng liên quan trực tiếp "
        "đến câu hỏi của người dùng. Điểm score thể hiện mức độ tương đồng khi truy xuất từ Qdrant; "
        "score thấp hơn ngưỡng của agent nghĩa là độ tin cậy thấp hơn, nhưng vẫn có thể dùng nếu nội dung "
        "khớp rõ với câu hỏi. Nếu các đoạn này không liên quan, hãy bỏ qua và trả lời theo system prompt "
        "cùng lịch sử hội thoại.\n"
        + "\n".join(lines)
    )
