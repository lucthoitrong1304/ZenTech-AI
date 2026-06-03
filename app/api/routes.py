from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRespondRequest, ChatRespondResponse
from app.services.chat_service import generate_reply

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
