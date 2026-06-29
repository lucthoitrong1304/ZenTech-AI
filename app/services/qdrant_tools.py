import logging
from uuid import uuid4

from qdrant_client import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.core.logging_utils import truncate_text
from app.schemas.rag import QdrantDocument, QdrantSearchResult
from app.services.embedding_service import embed_text, embed_texts
from app.services.qdrant_client import build_qdrant_client

logger = logging.getLogger("ai-service.qdrant")


def ensure_collection(collection_name: str | None = None) -> None:
    client = build_qdrant_client()
    col_name = collection_name or settings.qdrant_knowledge_collection

    try:
        if client.collection_exists(collection_name=col_name):
            return

        logger.info("Creating Qdrant collection: collection=%s", col_name)
        client.create_collection(
            collection_name=col_name,
            vectors_config=models.VectorParams(
                size=settings.qdrant_vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("Qdrant collection created: collection=%s", col_name)
    except Exception:
        logger.error("Failed to ensure Qdrant collection: collection=%s", col_name, exc_info=True)
        raise


def insert_documents(documents: list[QdrantDocument], collection_name: str | None = None) -> None:
    valid_documents = [document for document in documents if document.content.strip()]
    col_name = collection_name or settings.qdrant_knowledge_collection
    if not valid_documents:
        logger.warning("Qdrant upsert skipped because there are no valid documents: collection=%s", col_name)
        return

    logger.info("Starting Qdrant upsert: collection=%s documents=%s", col_name, len(valid_documents))
    try:
        ensure_collection(col_name)
        embeddings = embed_texts([document.content for document in valid_documents])
        points = [
            models.PointStruct(
                id=document.id or str(uuid4()),
                vector=embedding,
                payload={
                    **(document.metadata or {}),
                    "content": document.content,
                    "source": document.source,
                    "metadata": document.metadata,
                    "datasetId": document.datasetId,
                    "documentId": document.documentId,
                    "agentIds": document.agentIds,
                },
            )
            for document, embedding in zip(valid_documents, embeddings, strict=True)
        ]

        build_qdrant_client().upsert(
            collection_name=col_name,
            points=points,
        )
        logger.info("Qdrant upsert completed: collection=%s points=%s", col_name, len(points))
    except Exception:
        logger.error("Qdrant upsert failed: collection=%s", col_name, exc_info=True)
        raise


def search_documents(
    query: str,
    limit: int | None = None,
    dataset_ids: list[str] | None = None,
    score_threshold: float | None = None,
    collection_name: str | None = None,
) -> list[QdrantSearchResult]:
    clean_query = query.strip()
    col_name = collection_name or settings.qdrant_knowledge_collection
    effective_limit = limit or settings.qdrant_search_limit
    if not clean_query:
        logger.warning("Qdrant search skipped because query is empty: collection=%s", col_name)
        return []
    if not settings.qdrant_url or not settings.embedding_deployment_name:
        logger.warning("Qdrant search skipped because Qdrant URL or embedding deployment is not configured: collection=%s", col_name)
        return []

    logger.info(
        "Starting Qdrant search: collection=%s limit=%s dataset_count=%s threshold=%s query_preview='%s'",
        col_name,
        effective_limit,
        len(dataset_ids or []),
        score_threshold,
        truncate_text(clean_query, 150),
    )

    client = build_qdrant_client()
    try:
        if not client.collection_exists(collection_name=col_name):
            logger.warning("Qdrant collection does not exist: collection=%s", col_name)
            return []
    except UnexpectedResponse:
        logger.error("Failed to check Qdrant collection: collection=%s", col_name, exc_info=True)
        return []

    try:
        query_filter = build_dataset_filter(dataset_ids or []) if dataset_ids else None
        response = client.query_points(
            collection_name=col_name,
            query=embed_text(clean_query),
            limit=effective_limit,
            query_filter=query_filter,
            with_payload=True,
        )
    except Exception:
        logger.error("Qdrant search failed: collection=%s", col_name, exc_info=True)
        return []

    results: list[QdrantSearchResult] = []
    for point in response.points:
        payload = point.payload or {}
        content = payload.get("content") or payload.get("searchText") or ""
        if not isinstance(content, str) or not content.strip():
            continue

        source = payload.get("source")
        metadata = payload.get("metadata") or {k: v for k, v in payload.items() if k not in ("content", "searchText")}
        score = float(point.score)
        if score_threshold is not None and score < score_threshold:
            continue

        dataset_id = payload.get("datasetId")
        document_id = payload.get("documentId")
        results.append(
            QdrantSearchResult(
                id=point.id,
                content=content,
                score=score,
                source=source if isinstance(source, str) else None,
                metadata=metadata if isinstance(metadata, dict) else {},
                datasetId=dataset_id if isinstance(dataset_id, str) else None,
                documentId=document_id if isinstance(document_id, str) else None,
            )
        )

    if results:
        logger.info("Qdrant search completed: collection=%s results=%s", col_name, len(results))
    else:
        logger.warning("No suitable Qdrant context found: collection=%s", col_name)
    return results


def delete_document_points(document_id: str, collection_name: str | None = None) -> None:
    col_name = collection_name or settings.qdrant_knowledge_collection
    if not settings.qdrant_url:
        logger.warning("Qdrant delete skipped because Qdrant URL is not configured: collection=%s", col_name)
        return

    logger.info("Starting Qdrant document delete: collection=%s document_id=%s", col_name, document_id)
    client = build_qdrant_client()
    try:
        if not client.collection_exists(collection_name=col_name):
            logger.warning("Qdrant delete skipped because collection does not exist: collection=%s", col_name)
            return
    except UnexpectedResponse:
        logger.error("Failed to check Qdrant collection before delete: collection=%s", col_name, exc_info=True)
        return

    try:
        client.delete(
            collection_name=col_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="documentId",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )
        logger.info("Qdrant document delete completed: collection=%s document_id=%s", col_name, document_id)
    except Exception:
        logger.error("Qdrant document delete failed: collection=%s document_id=%s", col_name, document_id, exc_info=True)
        raise


def build_dataset_filter(dataset_ids: list[str]) -> models.Filter | None:
    clean_ids = [dataset_id for dataset_id in dataset_ids if dataset_id]
    if not clean_ids:
        return None

    return models.Filter(
        must=[
            models.FieldCondition(
                key="datasetId",
                match=models.MatchAny(any=clean_ids),
            )
        ]
    )
