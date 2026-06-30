import logging

from app.config import settings
from app.prompts.admin_chat_prompt import SYSTEM_PROMPT_ADMIN_CHAT
from app.schemas.admin_chat import AdminChatFollowUpRequest
from app.services.openai_client import build_client
from app.utils.code_reader import get_code_context_from_stack_trace

logger = logging.getLogger("ai-service.admin")
llm_logger = logging.getLogger("ai-service.llm")

def chat_follow_up(request: AdminChatFollowUpRequest) -> str:
    logger.info(
        "Received admin log chat follow-up request: service=%s user_message_length=%s history_length=%d",
        request.service,
        len(request.user_message or ""),
        len(request.history),
    )

    # Tìm mã nguồn lỗi từ log details
    code_context = get_code_context_from_stack_trace(request.service, request.log_details or "")

    # Khởi tạo chuỗi hội thoại
    user_context = f"Dịch vụ: {request.service}\nChi tiết: {request.log_details}"
    if code_context:
        user_context += f"\n=== MÃ NGUỒN GÂY LỖI THỰC TẾ ===\n{code_context}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_ADMIN_CHAT},
        {"role": "user", "content": user_context},
    ]

    # Đưa lịch sử chat vào
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})

    # Đưa tin nhắn mới nhất của user vào
    messages.append({"role": "user", "content": request.user_message})

    try:
        client = build_client()
        llm_logger.info("Starting LLM call for admin chat follow-up: model=%s", settings.azure_openai_model_name)
        
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.azure_openai_model_name,
                messages=messages,
                temperature=0.4,
            )
            content = response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=settings.azure_openai_model_name,
                input=messages,
            )
            content = response.output_text.strip()
            
        llm_logger.info("LLM call completed for admin chat follow-up: response_length=%s", len(content))
        logger.info("Admin chat follow-up completed successfully")
        return content
    except Exception:
        logger.error("Failed to generate admin chat follow-up response", exc_info=True)
        raise
