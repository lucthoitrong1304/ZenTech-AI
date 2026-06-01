import sys
from pathlib import Path

from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings


def build_client() -> OpenAI:
    return OpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
    )


def main() -> None:
    client = build_client()
    response = client.responses.create(
        model=settings.azure_openai_model_name,
        input="hi",
    )
    print(response.output_text)


if __name__ == "__main__":
    main()
