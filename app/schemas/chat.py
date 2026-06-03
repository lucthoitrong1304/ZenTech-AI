from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["customer", "assistant", "staff", "system"]
    content: str = Field(min_length=1, max_length=5000)


class ChatRespondRequest(BaseModel):
    conversationId: str = Field(min_length=1)
    messageId: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=5000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)


class ChatRespondResponse(BaseModel):
    content: str
