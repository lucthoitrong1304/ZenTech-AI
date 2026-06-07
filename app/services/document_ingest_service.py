import base64
import io
from uuid import uuid4

from app.schemas.agent import KnowledgeIngestRequest
from app.schemas.rag import QdrantDocument
from app.services.qdrant_tools import delete_document_points, insert_documents

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


def extract_text(content_base64: str, content_type: str, file_name: str) -> str:
    raw = base64.b64decode(content_base64)
    lower_name = file_name.lower()
    if content_type == "application/pdf" or lower_name.endswith(".pdf"):
        return extract_pdf_text(raw)
    return raw.decode("utf-8", errors="ignore")


def extract_pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page.strip() for page in pages if page.strip())


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
