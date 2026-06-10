from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["customer", "assistant", "staff", "system"]
    content: str = Field(min_length=1, max_length=5000)


class ChatAttachment(BaseModel):
    fileName: str = Field(min_length=1, max_length=255)
    contentType: str = Field(default="application/octet-stream", max_length=100)
    attachmentType: Literal["IMAGE", "VIDEO", "FILE"]
    mediaUrl: str | None = None
    contentBase64: str | None = None


class ChatRespondRequest(BaseModel):
    conversationId: str = Field(min_length=1)
    messageId: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=5000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)
    attachments: list[ChatAttachment] = Field(default_factory=list, max_length=10)


class ChatRespondResponse(BaseModel):
    content: str
