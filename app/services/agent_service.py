import logging
from typing import Generator

from app.config import settings
from app.schemas.agent import AgentRespondRequest, AgentRespondResponse, RetrievedContextResponse
from app.services.context_router import decide_context_tools
from app.services.openai_client import build_client
from app.services.tool_orchestrator import execute_tool_plan
from app.prompts.agent_prompt import build_agent_model_input

logger = logging.getLogger("ai-service")


def generate_agent_reply(request: AgentRespondRequest) -> AgentRespondResponse:
    logger.info(f"Generating agent reply for user request: {request.message}")
    
    # 1. Intent routing and tool planning
    route = decide_context_tools(request)
    
    # 2. Execute tools based on plan
    orchestrator_results = execute_tool_plan(request, route)
    
    # 3. Build model input prompt
    messages = build_agent_model_input(request, orchestrator_results)
    
    # 4. Invoke LLM (non-streaming)
    client = build_client()
    try:
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.chat_deployment_name,
                messages=messages,
                temperature=request.agent.temperature,
                max_completion_tokens=request.agent.maxTokens,
            )
            content = response.choices[0].message.content.strip()
        else:
            response = client.responses.create(
                model=settings.chat_deployment_name,
                input=messages,
            )
            content = response.output_text.strip()
            
        logger.info("Successfully generated non-streaming AI response.")
        
        # Format context responses for debug
        retrieved_context = []
        knowledge_context = orchestrator_results.get("knowledge_context", [])
        for item in knowledge_context:
            retrieved_context.append(
                RetrievedContextResponse(
                    id=str(item.id),
                    content=item.content,
                    score=item.score,
                    source=item.source,
                    datasetId=item.datasetId,
                    documentId=item.documentId,
                )
            )

        return AgentRespondResponse(
            content=content,
            fallback=False,
            handoffRecommended=(route.intent == "HUMAN_HANDOFF"),
            retrievedContext=retrieved_context,
            # We can include debugInfo in businessContext or extra fields
        )
    except Exception as ex:
        logger.error(f"Error calling LLM: {str(ex)}")
        fallback_msg = request.agent.fallbackMessage or "Tôi chưa có đủ thông tin để trả lời câu hỏi này."
        return AgentRespondResponse(
            content=fallback_msg,
            fallback=True,
            handoffRecommended=True,
            retrievedContext=[]
        )


def generate_agent_reply_stream(request: AgentRespondRequest) -> Generator[str, None, None]:
    logger.info(f"Generating streaming agent reply for: {request.message}")
    
    route = decide_context_tools(request)
    orchestrator_results = execute_tool_plan(request, route)
    messages = build_agent_model_input(request, orchestrator_results)
    
    client = build_client()
    try:
        if hasattr(client, "chat"):
            response = client.chat.completions.create(
                model=settings.chat_deployment_name,
                messages=messages,
                temperature=request.agent.temperature,
                max_completion_tokens=request.agent.maxTokens,
                stream=True
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            # Fallback for wrapper
            response = client.responses.create(
                model=settings.chat_deployment_name,
                input=messages,
            )
            yield response.output_text
    except Exception as ex:
        logger.error(f"Error calling LLM stream: {str(ex)}")
        yield request.agent.fallbackMessage or "Tôi chưa có đủ thông tin để trả lời câu hỏi này."
