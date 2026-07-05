from typing import Any

from pydantic import BaseModel, Field

from app.schemas.chat import ChatHistoryMessage, ChatAttachment
from app.schemas.rag import QdrantSearchResult


class RuntimeAgentConfig(BaseModel):
    id: str
    name: str
    systemPrompt: str = Field(min_length=1)
    guardrails: str | None = None
    temperature: float = Field(default=0.3, ge=0, le=2)
    maxTokens: int = Field(default=1000, ge=100, le=8000)
    topK: int = Field(default=5, ge=1, le=20)
    scoreThreshold: float = Field(default=0.72, ge=0, le=1)
    fallbackMessage: str | None = None
    handoffEnabled: bool = True
    handoffThreshold: float = Field(default=0.5, ge=0, le=1)


class AgentRespondRequest(BaseModel):
    agent: RuntimeAgentConfig
    role: str
    message: str = Field(min_length=1, max_length=5000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)
    attachments: list[ChatAttachment] = Field(default_factory=list, max_length=10)
    datasetIds: list[str] = Field(default_factory=list)
    businessContext: dict[str, Any] = Field(default_factory=dict)


class RetrievedContextResponse(BaseModel):
    id: str | int
    content: str
    score: float
    source: str | None = None
    datasetId: str | None = None
    documentId: str | None = None


class RecommendedProductResponse(BaseModel):
    productId: str
    variantId: str | None = None
    name: str
    imageKey: str
    price: float
    originalPrice: float | None = None
    salePrice: float | None = None
    saleStartAt: str | None = None
    saleEndAt: str | None = None
    stock: int


class AgentRespondResponse(BaseModel):
    content: str
    fallback: bool = False
    handoffRecommended: bool = False
    retrievedContext: list[RetrievedContextResponse] = Field(default_factory=list)
    recommendedProducts: list[RecommendedProductResponse] = Field(default_factory=list)


class KnowledgeIngestRequest(BaseModel):
    datasetId: str
    documentId: str
    agentIds: list[str] = Field(default_factory=list)
    fileName: str
    contentType: str
    contentBase64: str


class KnowledgeIngestResponse(BaseModel):
    chunkCount: int
