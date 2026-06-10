from uuid import uuid4

from app.schemas.agent import KnowledgeIngestRequest
from app.schemas.rag import QdrantDocument
from app.services.qdrant_tools import delete_document_points, insert_documents
from app.utils.document_text import extract_text

MAX_CHUNK_SIZE = 1200
CHUNK_OVERLAP = 160


def ingest_document(request: KnowledgeIngestRequest) -> int:
    text = extract_text(request.contentBase64, request.contentType, request.fileName)
    chunks = chunk_text(text)
    documents = [
        QdrantDocument(
            id=str(uuid4()),
            content=chunk,
            source=request.fileName,
            datasetId=request.datasetId,
            documentId=request.documentId,
            agentIds=request.agentIds,
            metadata={
                "fileName": request.fileName,
                "contentType": request.contentType,
                "chunkIndex": index,
                "datasetId": request.datasetId,
                "documentId": request.documentId,
            },
        )
        for index, chunk in enumerate(chunks)
    ]

    delete_document_points(request.documentId)
    insert_documents(documents)
    return len(documents)


def chunk_text(text: str) -> list[str]:
    clean_text = " ".join(text.split())
    if not clean_text:
        raise ValueError("Document does not contain readable text")

    chunks: list[str] = []
    start = 0
    while start < len(clean_text):
        end = min(start + MAX_CHUNK_SIZE, len(clean_text))
        chunks.append(clean_text[start:end].strip())
        if end == len(clean_text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [chunk for chunk in chunks if chunk]
