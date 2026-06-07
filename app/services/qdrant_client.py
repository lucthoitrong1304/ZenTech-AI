from qdrant_client import QdrantClient

from app.config import settings


def build_qdrant_client() -> QdrantClient:
    if not settings.qdrant_url:
        raise ValueError("QDRANT_URL is not configured")

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
