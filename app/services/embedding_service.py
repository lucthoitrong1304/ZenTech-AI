import logging

from app.config import settings
from app.core.logging_utils import truncate_text
from app.services.openai_client import build_client

logger = logging.getLogger("ai-service.embedding")


def embed_text(text: str) -> list[float]:
    embeddings = embed_texts([text])
    return embeddings[0] if embeddings else []


def embed_texts(texts: list[str]) -> list[list[float]]:
    clean_texts = [text.strip() for text in texts if text.strip()]
    if not clean_texts:
        logger.warning("Embedding skipped because input text list is empty")
        return []

    if not settings.embedding_deployment_name:
        logger.error("Embedding deployment name is not configured")
        raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME is not configured")

    logger.info(
        "Starting embedding: count=%s preview='%s'",
        len(clean_texts),
        truncate_text(clean_texts[0], 150),
    )

    try:
        response = build_client(base_url=settings.embedding_endpoint).embeddings.create(
            model=settings.embedding_deployment_name,
            input=clean_texts,
        )
        embeddings = [item.embedding for item in response.data]
        logger.info("Embedding completed: vectors=%s", len(embeddings))
        return embeddings
    except Exception:
        logger.error("Embedding failed", exc_info=True)
        raise
