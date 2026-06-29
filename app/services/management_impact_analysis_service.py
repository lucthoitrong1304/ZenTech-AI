import logging

from app.config import settings
from app.prompts.management_impact_analysis_prompt import SYSTEM_PROMPT_IMPACT
from app.schemas.management_impact_analysis import ManagementImpactAnalyzeRequest
from app.services.openai_client import build_client

logger = logging.getLogger("ai-service.management")
llm_logger = logging.getLogger("ai-service.llm")

def analyze_management_impact(request: ManagementImpactAnalyzeRequest) -> str:
    logger.info("Received management impact analysis request: incident_code=%s service=%s severity=%s", request.incidentCode, request.serviceName, request.severity)
    formatted_loss = f"{request.revenueLoss:,.0f}" if request.revenueLoss else "0"
    formatted_actual_rev = f"{request.actualRevenue:,.0f}" if request.actualRevenue else "0"
    formatted_expected_rev = f"{request.expectedRevenue:,.0f}" if request.expectedRevenue else "0"
    
    prompt = SYSTEM_PROMPT_IMPACT.format(
        incidentCode=request.incidentCode,
        serviceName=request.serviceName,
        apiPath=request.apiPath,
        httpMethod=request.httpMethod,
        statusCode=request.statusCode,
        durationMinutes=request.durationMinutes,
        actualRevenue=formatted_actual_rev,
        expectedRevenue=formatted_expected_rev,
        revenueLoss=formatted_loss,
        actualOrders=request.actualOrders,
        expectedOrders=request.expectedOrders,
        lostOrders=request.lostOrders,
        affectedUsers=request.affectedUsers,
        severity=request.severity
    )
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Hãy lập báo cáo phân tích tác động kinh doanh chi tiết cho sự cố: {request.incidentCode}."}
    ]
    
    try:
        client = build_client()
        llm_logger.info("Starting LLM call for management impact analysis: model=%s incident_code=%s", settings.azure_openai_model_name, request.incidentCode)
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
        llm_logger.info("LLM call completed for management impact analysis: response_length=%s", len(content))
        logger.info("Management impact analysis completed: incident_code=%s", request.incidentCode)
        return content
    except Exception:
        logger.error("Failed to analyze management impact", exc_info=True)
        raise
