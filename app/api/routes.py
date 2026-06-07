from fastapi import APIRouter, HTTPException

from app.schemas.agent import (
    AgentRespondRequest,
    AgentRespondResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
)
from app.schemas.chat import ChatRespondRequest, ChatRespondResponse
from app.services.agent_service import generate_agent_reply
from app.services.chat_service import generate_reply
from app.services.document_ingest_service import ingest_document
from app.services.qdrant_tools import delete_document_points

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return {"message": "ZenTech AI service is running"}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat/respond", response_model=ChatRespondResponse)
def respond_to_chat(request: ChatRespondRequest) -> ChatRespondResponse:
    try:
        content = generate_reply(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to generate a response") from exc

    if not content:
        raise HTTPException(status_code=502, detail="AI service returned an empty response")

    return ChatRespondResponse(content=content)


@router.post("/agents/respond", response_model=AgentRespondResponse)
def respond_as_agent(request: AgentRespondRequest) -> AgentRespondResponse:
    try:
        response = generate_agent_reply(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI agent failed to generate a response") from exc

    if not response.content:
        raise HTTPException(status_code=502, detail="AI agent returned an empty response")

    return response


@router.post("/knowledge/documents/ingest", response_model=KnowledgeIngestResponse)
def ingest_knowledge_document(request: KnowledgeIngestRequest) -> KnowledgeIngestResponse:
    try:
        chunk_count = ingest_document(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Document ingest failed") from exc

    return KnowledgeIngestResponse(chunkCount=chunk_count)


@router.delete("/knowledge/documents/{document_id}")
def delete_knowledge_document(document_id: str) -> dict[str, str]:
    try:
        delete_document_points(document_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Document delete failed") from exc

    return {"status": "deleted"}
