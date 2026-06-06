from pydantic import BaseModel, Field

class AdminLogExplainRequest(BaseModel):
    log_message: str = Field(..., description="Thông điệp chính của log lỗi")
    log_details: str = Field(..., description="Chi tiết đầy đủ (raw log/stack trace) của log lỗi")
    service: str = Field(..., description="Tên dịch vụ phát sinh log (BACKEND/FRONTEND/AI-SERVICE)")

class AdminLogExplainResponse(BaseModel):
    explanation: str = Field(..., description="Nội dung giải thích lỗi của AI bằng tiếng Việt")
