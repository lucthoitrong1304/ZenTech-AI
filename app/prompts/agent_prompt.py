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
        + "Che do demo agent: hay hanh xu nhu agent dang tu van truc tiep trong san pham. "
        + "Tra loi tu nhien theo prompt, role va lich su hoi thoai, nhung khong duoc mo rong "
        + "pham vi ngoai system prompt/guardrails cua agent. Dataset/Qdrant chi la nguon tham "
        + "khao bo sung khi co lien quan va du tin cay. Neu khong co retrieved context phu hop, "
        + "agent van co the chao hoi, tu gioi thieu hoac hoi them thong tin, nhung khong duoc tu "
        + "suy doan kien thuc, dinh nghia hay tu van ngoai pham vi duoc cau hinh. Neu cau hoi "
        + "ngoai pham vi ho tro, hay lich su tu choi theo system prompt va goi y nguoi dung cung "
        + "cap them thong tin lien quan den ZenTech."
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
        "Ngu canh tu dataset cua agent. Chi dung cac doan nay khi chung lien quan den cau hoi. "
        "Score thap hon nguong agent co nghia la do tin cay thap hon, nhung van co the dung neu "
        "noi dung truc tiep khop voi cau hoi. Neu cac doan nay khong lien quan, hay bo qua va "
        "tra loi theo prompt/lich su hoi thoai.\n"
        + "\n".join(lines)
    )
