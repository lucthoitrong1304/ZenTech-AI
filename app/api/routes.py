from fastapi import APIRouter, HTTPException

from app.schemas.agent import (
    AgentRespondRequest,
    AgentRespondResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
)
from app.services.agent_service import generate_agent_reply
from app.schemas.management_reports import ReportAnalyzeRequest, ReportAnalyzeResponse
from app.services.management_reports_service import analyze_report_data
from app.services.document_ingest_service import ingest_document
from app.services.qdrant_tools import delete_document_points

from app.schemas.admin_logs import AdminLogExplainRequest, AdminLogExplainResponse
from app.services.admin_logs_service import explain_log_error

from app.schemas.inventory_management import InventoryRecommendRequest, InventoryRecommendResponse
from app.services.inventory_management_service import generate_inventory_recommendation

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return {"message": "ZenTech AI service is running"}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}



@router.post("/management/analyze/report", response_model=ReportAnalyzeResponse)
def analyze_report(request: ReportAnalyzeRequest) -> ReportAnalyzeResponse:
    try:
        content = analyze_report_data(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to analyze report") from exc

    if not content:
        raise HTTPException(status_code=502, detail="AI service returned an empty report analysis")

    return ReportAnalyzeResponse(content=content)


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

@router.post("/admin/logs/explain", response_model=AdminLogExplainResponse)
def explain_log(request: AdminLogExplainRequest) -> AdminLogExplainResponse:
    try:
        explanation = explain_log_error(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to explain log error") from exc

    if not explanation:
        raise HTTPException(status_code=502, detail="AI service returned an empty explanation")

    return AdminLogExplainResponse(explanation=explanation)


@router.post("/management/inventory/recommend", response_model=InventoryRecommendResponse)
def recommend_inventory(request: InventoryRecommendRequest) -> InventoryRecommendResponse:
    try:
        content = generate_inventory_recommendation(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to recommend inventory restocks") from exc

    if not content:
        raise HTTPException(status_code=502, detail="AI service returned an empty recommendation content")

    return InventoryRecommendResponse(content=content)

