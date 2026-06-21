import logging
from app.config import settings
from app.schemas.rag import QdrantSearchResult
from app.services.qdrant_tools import search_documents

logger = logging.getLogger("ai-service")


def search_knowledge(
    query: str,
    dataset_ids: list[str],
    limit: int = 5,
    score_threshold: float | None = None
) -> list[QdrantSearchResult]:
    logger.info(f"Searching knowledge_vectors with query: {query} and datasets: {dataset_ids}")
    try:
        return search_documents(
            query=query,
            limit=limit,
            dataset_ids=dataset_ids,
            score_threshold=score_threshold,
            collection_name=settings.qdrant_knowledge_collection
        )
    except Exception as ex:
        logger.error(f"Error searching knowledge_vectors: {str(ex)}")
        return []
