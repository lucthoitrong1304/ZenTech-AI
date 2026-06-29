import logging

from app.config import settings
from app.prompts.management_reports_prompt import SYSTEM_PROMPT_REPORT
from app.schemas.management_reports import ReportAnalyzeRequest
from app.services.openai_client import build_client

logger = logging.getLogger("ai-service.management")
llm_logger = logging.getLogger("ai-service.llm")


def analyze_report_data(request: ReportAnalyzeRequest) -> str:
    logger.info("Received management report analysis request: category=%s data_length=%s", request.category, len(str(request.data)))
    prompt = SYSTEM_PROMPT_REPORT.format(category=request.category)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Dữ liệu:\n{request.data}"},
    ]

    try:
        client = build_client()
        llm_logger.info("Starting LLM call for management report analysis: model=%s category=%s", settings.azure_openai_model_name, request.category)
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
        llm_logger.info("LLM call completed for management report analysis: response_length=%s", len(content))
        logger.info("Management report analysis completed: category=%s", request.category)
        return content
    except Exception:
        logger.error("Failed to analyze management report data", exc_info=True)
        raise
