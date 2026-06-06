from app.config import settings
from app.prompts.chat_prompt import build_model_input
from app.schemas.rag import QdrantSearchResult
from app.schemas.chat import ChatRespondRequest
from app.services.openai_client import build_client
from app.services.qdrant_tools import search_documents


def generate_reply(request: ChatRespondRequest) -> str:
    retrieved_context = find_relevant_context(request.message)
    response = build_client().responses.create(
        model=settings.chat_deployment_name,
        input=build_model_input(request, retrieved_context=retrieved_context),
    )
    return response.output_text.strip()


def find_relevant_context(message: str) -> list[QdrantSearchResult]:
    if not settings.qdrant_url or not settings.embedding_deployment_name:
        return []

    try:
        return search_documents(message)
    except Exception:
        return []
