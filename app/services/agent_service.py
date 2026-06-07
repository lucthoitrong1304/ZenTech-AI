from app.prompts.agent_prompt import build_agent_model_input
from app.config import settings
from app.schemas.agent import AgentRespondRequest, AgentRespondResponse, RetrievedContextResponse
from app.schemas.rag import QdrantSearchResult
from app.services.context_router import decide_context_tools
from app.services.openai_client import build_client
from app.services.qdrant_tools import search_documents


def generate_agent_reply(request: AgentRespondRequest) -> AgentRespondResponse:
    retrieved_context = find_agent_context(request)

    response = build_client().responses.create(
        model=settings.chat_deployment_name,
        input=build_agent_model_input(request, retrieved_context),
        temperature=request.agent.temperature,
        max_output_tokens=request.agent.maxTokens,
    )

    return AgentRespondResponse(
        content=response.output_text.strip(),
        fallback=False,
        handoffRecommended=False,
        retrievedContext=[to_context_response(item) for item in retrieved_context],
    )


def find_agent_context(request: AgentRespondRequest) -> list[QdrantSearchResult]:
    route = decide_context_tools(request)
    if "knowledge_search" not in route.tools:
        return []

    try:
        # Return top candidates first. The UI needs to show their scores so users can tune
        # the agent threshold instead of seeing an opaque fallback.
        return search_documents(
            request.message,
            limit=request.agent.topK,
            dataset_ids=request.datasetIds,
            score_threshold=None,
        )
    except Exception:
        return []


def to_context_response(item: QdrantSearchResult) -> RetrievedContextResponse:
    return RetrievedContextResponse(
        id=item.id,
        content=item.content,
        score=item.score,
        source=item.source,
        datasetId=item.datasetId,
        documentId=item.documentId,
    )
