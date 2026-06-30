from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.schemas.agent import (
    AgentRespondRequest,
    AgentRespondResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
)
from app.schemas.product import (
    ProductSyncRequest,
    ProductSyncResponse,
    ProductVectorVerifyRequest,
    ProductVectorVerifyResponse,
    ProductVectorVerifyResult,
)
from app.schemas.rag import QdrantDocument
from app.services.agent_service import generate_agent_reply, generate_agent_reply_stream
from app.schemas.management_reports import ReportAnalyzeRequest, ReportAnalyzeResponse
from app.services.management_reports_service import analyze_report_data
from app.schemas.management_impact_analysis import ManagementImpactAnalyzeRequest, ManagementImpactAnalyzeResponse
from app.services.management_impact_analysis_service import analyze_management_impact
from app.services.document_ingest_service import ingest_document
from app.services.qdrant_client import build_qdrant_client
from app.services.qdrant_tools import count_product_variant_points, delete_document_points, insert_documents, ensure_collection

from app.schemas.admin_logs import AdminLogExplainRequest, AdminLogExplainResponse
from app.services.admin_logs_service import explain_log_error

from app.schemas.admin_chat import AdminChatFollowUpRequest, AdminChatFollowUpResponse
from app.services.admin_chat_service import chat_follow_up

from app.schemas.admin_incidents import IncidentAnalyzeRequest, IncidentAnalyzeResponse
from app.services.admin_incidents_service import analyze_incident_data

from app.schemas.inventory_management import InventoryRecommendRequest, InventoryRecommendResponse
from app.services.inventory_management_service import generate_inventory_recommendation
from app.schemas.admin_activity_timeline import ActivityTimelineSummaryRequest, ActivityTimelineSummaryResponse
from app.services.admin_activity_timeline_service import summarize_activity_timeline

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


@router.post("/management/analyze/impact", response_model=ManagementImpactAnalyzeResponse)
def analyze_impact(request: ManagementImpactAnalyzeRequest) -> ManagementImpactAnalyzeResponse:
    try:
        ai_summary = analyze_management_impact(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to analyze business impact") from exc

    if not ai_summary:
        raise HTTPException(status_code=502, detail="AI service returned an empty business impact analysis")

    return ManagementImpactAnalyzeResponse(aiSummary=ai_summary)


@router.post("/agents/respond", response_model=AgentRespondResponse)
def respond_as_agent(request: AgentRespondRequest) -> AgentRespondResponse:
    try:
        response = generate_agent_reply(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI agent failed to generate a response: {str(exc)}") from exc

    if not response.content:
        raise HTTPException(status_code=502, detail="AI agent returned an empty response")

    return response


@router.post("/agents/respond/stream")
def respond_as_agent_stream(request: AgentRespondRequest):
    try:
        generator = generate_agent_reply_stream(request)
        return StreamingResponse(generator, media_type="text/event-stream")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI agent failed to generate stream response: {str(exc)}") from exc


@router.post("/knowledge/documents/ingest", response_model=KnowledgeIngestResponse)
def ingest_knowledge_document(request: KnowledgeIngestRequest) -> KnowledgeIngestResponse:
    try:
        # Document ingest logic currently uses settings.qdrant_collection_name
        # To maintain backward compatibility, we ensure the documents ingest into qdrant_knowledge_collection
        chunk_count = ingest_document(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Document ingest failed: {str(exc)}") from exc

    return KnowledgeIngestResponse(chunkCount=chunk_count)


@router.delete("/knowledge/documents/{document_id}")
def delete_knowledge_document(document_id: str) -> dict[str, str]:
    try:
        delete_document_points(document_id, settings.qdrant_knowledge_collection)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Document delete failed") from exc

    return {"status": "deleted"}


@router.post("/api/internal/products/sync", response_model=ProductSyncResponse)
def sync_products(request: ProductSyncRequest) -> ProductSyncResponse:
    try:
        documents = []
        for item in request.variants:
            doc_id = item.variantId or item.productId
            metadata = {
                "productId": item.productId,
                "variantId": item.variantId,
                "sku": item.sku,
                "name": item.name,
                "categoryId": item.categoryId,
                "categoryName": item.categoryName,
                "brandId": item.brandId,
                "brandName": item.brandName,
                "colors": item.colors,
                "sizes": item.sizes,
                "material": item.material,
                "tags": item.tags,
                "imageKeys": item.imageKeys,
                "status": item.status,
                "updatedAt": item.updatedAt
            }
            documents.append(
                QdrantDocument(
                    content=item.searchText,
                    id=doc_id,
                    metadata=metadata,
                    source="product_db"
                )
            )
        insert_documents(documents, collection_name=settings.qdrant_product_collection)
        return ProductSyncResponse(processedCount=len(request.variants))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Products sync failed: {str(exc)}") from exc


@router.post("/api/internal/products/reindex")
def reindex_products() -> dict[str, str]:
    client = build_qdrant_client()
    col_name = settings.qdrant_product_collection
    try:
        if client.collection_exists(col_name):
            client.delete_collection(col_name)
        ensure_collection(col_name)
        return {"status": "reindexed"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Reindex failed: {str(exc)}") from exc


@router.post("/api/internal/products/verify", response_model=ProductVectorVerifyResponse)
def verify_products(request: ProductVectorVerifyRequest) -> ProductVectorVerifyResponse:
    try:
        results = []
        for item in request.items:
            count = count_product_variant_points(
                product_id=item.productId,
                variant_id=item.variantId,
                collection_name=settings.qdrant_product_collection,
            )
            results.append(
                ProductVectorVerifyResult(
                    productId=item.productId,
                    variantId=item.variantId,
                    present=count > 0,
                    pointCount=count,
                )
            )
        return ProductVectorVerifyResponse(items=results)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Product verify failed: {str(exc)}") from exc


@router.post("/admin/logs/explain", response_model=AdminLogExplainResponse)
def explain_log(request: AdminLogExplainRequest) -> AdminLogExplainResponse:
    try:
        explanation = explain_log_error(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to explain log error") from exc

    if not explanation:
        raise HTTPException(status_code=502, detail="AI service returned an empty explanation")

    return AdminLogExplainResponse(explanation=explanation)


@router.post("/admin/chat/follow-up", response_model=AdminChatFollowUpResponse)
def follow_up_chat(request: AdminChatFollowUpRequest) -> AdminChatFollowUpResponse:
    try:
        content = chat_follow_up(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to generate chat follow-up") from exc

    if not content:
        raise HTTPException(status_code=502, detail="AI service returned an empty chat follow-up")

    return AdminChatFollowUpResponse(content=content)


@router.post("/admin/incidents/analyze", response_model=IncidentAnalyzeResponse)
def analyze_incident(request: IncidentAnalyzeRequest) -> IncidentAnalyzeResponse:
    try:
        response = analyze_incident_data(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to analyze incident") from exc

    return response


@router.post("/admin/activity-timeline/summary", response_model=ActivityTimelineSummaryResponse)
def summarize_activity_timeline_route(request: ActivityTimelineSummaryRequest) -> ActivityTimelineSummaryResponse:
    try:
        lines = summarize_activity_timeline(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to summarize activity timeline") from exc

    if not lines:
        raise HTTPException(status_code=502, detail="AI service returned an empty timeline summary")

    return ActivityTimelineSummaryResponse(lines=lines)


@router.post("/management/inventory/recommend", response_model=InventoryRecommendResponse)
def recommend_inventory(request: InventoryRecommendRequest) -> InventoryRecommendResponse:
    try:
        content = generate_inventory_recommendation(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to recommend inventory restocks") from exc

    if not content:
        raise HTTPException(status_code=502, detail="AI service returned an empty recommendation content")

    return InventoryRecommendResponse(content=content)
