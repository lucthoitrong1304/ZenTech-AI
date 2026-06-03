from openai import OpenAI

from app.config import settings


def build_client() -> OpenAI:
    return OpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
    )
