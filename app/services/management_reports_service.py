from app.config import settings
from app.prompts.management_reports_prompt import SYSTEM_PROMPT_REPORT
from app.schemas.management_reports import ReportAnalyzeRequest
from app.services.openai_client import build_client

def analyze_report_data(request: ReportAnalyzeRequest) -> str:
    prompt = SYSTEM_PROMPT_REPORT.format(category=request.category)
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Dữ liệu:\n{request.data}"}
    ]
    
    try:
        client = build_client()
        # Handle standard OpenAI SDK
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.azure_openai_model_name,
                messages=messages,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        else:
            # Fallback to weird mock/wrapper if present
            response = client.responses.create(
                model=settings.azure_openai_model_name,
                input=messages,
            )
            return response.output_text.strip()
    except Exception as e:
        raise e
