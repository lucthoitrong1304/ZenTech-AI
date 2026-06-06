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
            },
        )
        for document, embedding in zip(valid_documents, embeddings, strict=True)
    ]

    build_qdrant_client().upsert(
        collection_name=settings.qdrant_collection_name,
        points=points,
    )


def search_documents(query: str, limit: int | None = None) -> list[QdrantSearchResult]:
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

    response = client.query_points(
        collection_name=settings.qdrant_collection_name,
        query=embed_text(clean_query),
        limit=limit or settings.qdrant_search_limit,
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
        results.append(
            QdrantSearchResult(
                id=point.id,
                content=content,
                score=point.score,
                source=source if isinstance(source, str) else None,
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )
    return results
