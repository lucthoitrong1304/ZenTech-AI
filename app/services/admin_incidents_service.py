import json
import logging
from app.config import settings
from app.prompts.admin_incidents_prompt import SYSTEM_PROMPT_ADMIN_INCIDENTS
from app.schemas.admin_incidents import IncidentAnalyzeRequest, IncidentAnalyzeResponse
from app.services.openai_client import build_client

logger = logging.getLogger(__name__)

def analyze_incident_data(request: IncidentAnalyzeRequest) -> IncidentAnalyzeResponse:
    # 1. Định dạng thông tin sự cố
    inc = request.incident
    incident_details = (
        f"Mã sự cố: {inc.code}\n"
        f"Dịch vụ: {inc.service_name}\n"
        f"API Path: {inc.api_path} ({inc.http_method})\n"
        f"Status Code: {inc.status_code}\n"
        f"Error Message: {inc.error_message}\n"
        f"Stack Trace: {inc.stack_trace[:1500]}\n"  # giới hạn độ dài stack trace
        f"Mức độ hiện tại: {inc.severity}\n"
    )

    # 2. Định dạng Loki logs liên quan
    logs_details = "\n".join(request.logs[:30])  # giới hạn 30 dòng log

    # 3. Định dạng Activity Logs của user
    activity_details = ""
    for idx, act in enumerate(request.activity_logs[:15]):
        activity_details += (
            f"- [{act.get('timestamp')}] {act.get('area')} | "
            f"Action: {act.get('action')} | "
            f"Summary: {act.get('summary')} | "
            f"Desc: {act.get('description')}\n"
        )

    # 4. Gom nhóm nội dung gửi LLM
    user_content = (
        f"=== THÔNG TIN SỰ CỐ ===\n{incident_details}\n"
        f"=== LOGS LIÊN QUAN (LOKI) ===\n{logs_details}\n"
        f"=== HÀNH VI USER TRƯỚC LỖI (ACTIVITY LOGS) ===\n{activity_details if activity_details else 'Không có dữ liệu hoạt động.'}\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_ADMIN_INCIDENTS},
        {"role": "user", "content": user_content}
    ]

    try:
        client = build_client()
        content = ""
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.azure_openai_model_name,
                messages=messages,
                temperature=0.2,
            )
            content = response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=settings.azure_openai_model_name,
                input=messages,
            )
            content = response.output_text.strip()

        # Làm sạch chuỗi phản hồi để phòng trường hợp LLM bọc trong ```json ... ```
        clean_content = content
        if clean_content.startswith("```json"):
            clean_content = clean_content[7:]
        if clean_content.endswith("```"):
            clean_content = clean_content[:-3]
        clean_content = clean_content.strip()

        data = json.loads(clean_content)

        return IncidentAnalyzeResponse(
            summary=data.get("summary", "Không có tóm tắt lỗi."),
            root_cause=data.get("root_cause", "Không xác định được nguyên nhân gốc."),
            severity_suggestion=data.get("severity_suggestion", "LOW"),
            solution_suggestion=data.get("solution_suggestion", "Không có giải pháp gợi ý."),
            confidence_score=float(data.get("confidence_score", 0.7))
        )

    except Exception as e:
        logger.error("Failed to analyze incident with OpenAI: %s", str(e))
        # Fallback response if OpenAI call or parsing fails
        return IncidentAnalyzeResponse(
            summary=f"Lỗi phân tích: {inc.error_message}",
            root_cause="Không thể kết nối hoặc parse kết quả từ AI Service.",
            severity_suggestion=inc.severity,
            solution_suggestion="Hãy kiểm tra logs chi tiết và thử lại sau.",
            confidence_score=0.0
        )
