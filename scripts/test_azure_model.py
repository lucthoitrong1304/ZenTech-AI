import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.services.openai_client import build_client


def main() -> None:
    client = build_client()
    response = client.responses.create(
        model=settings.azure_openai_model_name,
        input="hi",
    )
    print(response.output_text)


if __name__ == "__main__":
    main()
