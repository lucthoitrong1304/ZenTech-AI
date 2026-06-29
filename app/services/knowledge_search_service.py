import logging

from app.config import settings
from app.core.logging_utils import truncate_text
from app.schemas.rag import QdrantSearchResult
from app.services.qdrant_tools import search_documents

logger = logging.getLogger("ai-service.rag")


def search_knowledge(
    query: str,
    dataset_ids: list[str],
    limit: int = 5,
    score_threshold: float | None = None
) -> list[QdrantSearchResult]:
    logger.info(
        "Starting RAG knowledge search: dataset_count=%s limit=%s threshold=%s query_preview='%s'",
        len(dataset_ids),
        limit,
        score_threshold,
        truncate_text(query, 150),
    )
    try:
        results = search_documents(
            query=query,
            limit=limit,
            dataset_ids=dataset_ids,
            score_threshold=score_threshold,
            collection_name=settings.qdrant_knowledge_collection,
        )
        if results:
            logger.info("RAG knowledge search completed: contexts=%s", len(results))
        else:
            logger.warning("No suitable RAG context found")
        return results
    except Exception:
        logger.error("RAG knowledge search failed", exc_info=True)
        return []
