from typing import Any

from pydantic import BaseModel, Field


class QdrantDocument(BaseModel):
    content: str = Field(min_length=1)
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    id: int | str | None = None
    datasetId: str | None = None
    documentId: str | None = None
    agentIds: list[str] = Field(default_factory=list)


class QdrantSearchResult(BaseModel):
    id: int | str
    content: str
    score: float
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    datasetId: str | None = None
    documentId: str | None = None
