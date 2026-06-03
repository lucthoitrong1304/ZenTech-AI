from app.config import settings
from app.prompts.chat_prompt import build_model_input
from app.schemas.chat import ChatRespondRequest
from app.services.openai_client import build_client


def generate_reply(request: ChatRespondRequest) -> str:
    response = build_client().responses.create(
        model=settings.azure_openai_model_name,
        input=build_model_input(request),
    )
    return response.output_text.strip()
