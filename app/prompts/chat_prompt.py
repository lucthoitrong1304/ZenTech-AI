from app.schemas.chat import ChatRespondRequest
from app.schemas.rag import QdrantSearchResult
from app.utils.chat_roles import to_openai_role

SYSTEM_PROMPT = (
    "Ban la ZenTech AI, tro ly tu van khach hang cua cua hang ecommerce ZenTech. "
    "Tra loi ngan gon, lich su, bang tieng Viet. "
    "Chi tu van thong tin chung ve mua hang, bao hanh, giao hang, thanh toan, doi tra, "
    "va cach lien he nhan vien. Neu khong chac, hay de nghi khach hang gap nhan vien ho tro. "
    "Khong tu y khang dinh gia, ton kho, don hang hay voucher cu the khi khong co du lieu."
)

MAX_HISTORY_MESSAGES = 10


def build_model_input(
    request: ChatRespondRequest,
    retrieved_context: list[QdrantSearchResult] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    context_message = build_retrieved_context_message(retrieved_context or [])
    if context_message:
        messages.append({"role": "system", "content": context_message})

    for item in request.history[-MAX_HISTORY_MESSAGES:]:
        content = item.content.strip()
        if content:
            messages.append({"role": to_openai_role(item.role), "content": content})

    messages.append({"role": "user", "content": request.message.strip()})
    return messages


def build_retrieved_context_message(context: list[QdrantSearchResult]) -> str | None:
    if not context:
        return None

    context_lines = [
        f"- {item.content.strip()}"
        for item in context
        if item.content.strip()
    ]
    if not context_lines:
        return None

    return (
        "Ngu canh noi bo co the huu ich cho cau hoi hien tai. "
        "Chi dung neu phu hop voi cau hoi cua khach; neu ngu canh khong du ro, "
        "hay de nghi khach lien he nhan vien ho tro.\n"
        + "\n".join(context_lines)
    )
