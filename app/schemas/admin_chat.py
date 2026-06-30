from pydantic import BaseModel, Field
from typing import List

class ChatMessage(BaseModel):
    role: str = Field(..., description="Vai trò của tin nhắn (user/assistant)")
    content: str = Field(..., description="Nội dung của tin nhắn")

class AdminChatFollowUpRequest(BaseModel):
    service: str = Field(..., description="Tên dịch vụ phát sinh log (BACKEND/FRONTEND/AI-SERVICE)")
    log_details: str = Field(..., description="Chi tiết đầy đủ (raw log/stack trace) của log lỗi")
    user_message: str = Field(..., description="Câu hỏi tiếp nối của lập trình viên")
    history: List[ChatMessage] = Field(default=[], description="Lịch sử chat trước đó")

class AdminChatFollowUpResponse(BaseModel):
    content: str = Field(..., description="Câu trả lời tiếp nối của AI")
