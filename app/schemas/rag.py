from typing import Any

from pydantic import BaseModel, Field


class QdrantDocument(BaseModel):
    content: str = Field(min_length=1)
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    id: int | str | None = None


class QdrantSearchResult(BaseModel):
    id: int | str
    content: str
    score: float
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
