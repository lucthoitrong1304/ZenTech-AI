import logging

from app.config import settings
from app.prompts.admin_logs_prompt import SYSTEM_PROMPT_ADMIN_LOGS
from app.schemas.admin_logs import AdminLogExplainRequest
from app.services.openai_client import build_client

logger = logging.getLogger("ai-service.admin")
llm_logger = logging.getLogger("ai-service.llm")


def explain_log_error(request: AdminLogExplainRequest) -> str:
    logger.info(
        "Received admin log explanation request: service=%s message_length=%s details_length=%s",
        request.service,
        len(request.log_message or ""),
        len(request.log_details or ""),
    )
    user_content = f"Dịch vụ: {request.service}\nThông điệp: {request.log_message}\nChi tiết: {request.log_details}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_ADMIN_LOGS},
        {"role": "user", "content": user_content},
    ]

    try:
        client = build_client()
        llm_logger.info("Starting LLM call for admin log explanation: model=%s service=%s", settings.azure_openai_model_name, request.service)
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
        llm_logger.info("LLM call completed for admin log explanation: response_length=%s", len(content))
        logger.info("Admin log explanation completed: service=%s", request.service)
        return content
    except Exception:
        logger.error("Failed to explain admin log error", exc_info=True)
        raise
