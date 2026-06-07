from uuid import uuid4

from qdrant_client import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.schemas.rag import QdrantDocument, QdrantSearchResult
from app.services.embedding_service import embed_text, embed_texts
from app.services.qdrant_client import build_qdrant_client


def ensure_collection() -> None:
    client = build_qdrant_client()
    collection_name = settings.qdrant_collection_name

    if client.collection_exists(collection_name=collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=settings.qdrant_vector_size,
            distance=models.Distance.COSINE,
        ),
    )


def insert_documents(documents: list[QdrantDocument]) -> None:
    valid_documents = [document for document in documents if document.content.strip()]
    if not valid_documents:
        return

    ensure_collection()
    embeddings = embed_texts([document.content for document in valid_documents])
    points = [
        models.PointStruct(
            id=document.id or str(uuid4()),
            vector=embedding,
            payload={
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
        collection_name=settings.qdrant_collection_name,
        points=points,
    )


def search_documents(
    query: str,
    limit: int | None = None,
    dataset_ids: list[str] | None = None,
    score_threshold: float | None = None,
) -> list[QdrantSearchResult]:
    clean_query = query.strip()
    if not clean_query:
        return []
    if not settings.qdrant_url or not settings.embedding_deployment_name:
        return []

    client = build_qdrant_client()
    try:
        if not client.collection_exists(collection_name=settings.qdrant_collection_name):
            return []
    except UnexpectedResponse:
        return []

    query_filter = build_dataset_filter(dataset_ids or [])
    response = client.query_points(
        collection_name=settings.qdrant_collection_name,
        query=embed_text(clean_query),
        limit=limit or settings.qdrant_search_limit,
        query_filter=query_filter,
        with_payload=True,
    )

    results: list[QdrantSearchResult] = []
    for point in response.points:
        payload = point.payload or {}
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        source = payload.get("source")
        metadata = payload.get("metadata")
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
    return results


def delete_document_points(document_id: str) -> None:
    if not settings.qdrant_url:
        return

    client = build_qdrant_client()
    try:
        if not client.collection_exists(collection_name=settings.qdrant_collection_name):
            return
    except UnexpectedResponse:
        return

    client.delete(
        collection_name=settings.qdrant_collection_name,
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
