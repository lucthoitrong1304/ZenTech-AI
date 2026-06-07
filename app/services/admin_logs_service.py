from app.config import settings
from app.prompts.admin_logs_prompt import SYSTEM_PROMPT_ADMIN_LOGS
from app.schemas.admin_logs import AdminLogExplainRequest
from app.services.openai_client import build_client

def explain_log_error(request: AdminLogExplainRequest) -> str:
    user_content = f"Dịch vụ: {request.service}\nThông điệp: {request.log_message}\nChi tiết: {request.log_details}"
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_ADMIN_LOGS},
        {"role": "user", "content": user_content}
    ]
    
    try:
        client = build_client()
        # Hỗ trợ SDK tiêu chuẩn hoặc mock adapter
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.azure_openai_model_name,
                messages=messages,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=settings.azure_openai_model_name,
                input=messages,
            )
            return response.output_text.strip()
    except Exception as e:
        raise e
