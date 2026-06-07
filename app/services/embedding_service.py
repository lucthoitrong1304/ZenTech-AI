from app.config import settings
from app.services.openai_client import build_client


def embed_text(text: str) -> list[float]:
    embeddings = embed_texts([text])
    return embeddings[0] if embeddings else []


def embed_texts(texts: list[str]) -> list[list[float]]:
    clean_texts = [text.strip() for text in texts if text.strip()]
    if not clean_texts:
        return []

    if not settings.embedding_deployment_name:
        raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME is not configured")

    response = build_client(base_url=settings.embedding_endpoint).embeddings.create(
        model=settings.embedding_deployment_name,
        input=clean_texts,
    )
    return [item.embedding for item in response.data]
