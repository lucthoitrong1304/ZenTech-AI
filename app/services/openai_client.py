from openai import OpenAI

from app.config import settings


def build_client(base_url: str | None = None) -> OpenAI:
    return OpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=base_url or settings.azure_openai_endpoint,
    )
