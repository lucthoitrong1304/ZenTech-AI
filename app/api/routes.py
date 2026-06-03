from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRespondRequest, ChatRespondResponse
from app.services.chat_service import generate_reply
from app.schemas.management_reports import ReportAnalyzeRequest, ReportAnalyzeResponse
from app.services.management_reports_service import analyze_report_data

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

@router.post("/management/analyze/report", response_model=ReportAnalyzeResponse)
def analyze_report(request: ReportAnalyzeRequest) -> ReportAnalyzeResponse:
    try:
        content = analyze_report_data(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI service failed to analyze report") from exc

    if not content:
        raise HTTPException(status_code=502, detail="AI service returned an empty report analysis")

    return ReportAnalyzeResponse(content=content)
