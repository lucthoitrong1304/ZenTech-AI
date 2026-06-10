from app.schemas.agent import AgentRespondRequest
from app.schemas.rag import QdrantSearchResult
from app.utils.chat_roles import to_openai_role

MAX_HISTORY_MESSAGES = 10


def build_agent_model_input(
    request: AgentRespondRequest,
    retrieved_context: list[QdrantSearchResult],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
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

    messages.append({"role": "user", "content": request.message.strip()})
    return messages


def build_business_context_message(context: dict[str, object]) -> str | None:
    if not context:
        return None

    lines = [f"- {key}: {value}" for key, value in context.items() if value is not None]
    if not lines:
        return None
    return "Ngu canh he thong/kinh doanh hien tai:\n" + "\n".join(lines)


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
