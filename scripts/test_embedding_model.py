import sys
from pathlib import Path
from urllib.parse import urlparse

from openai import OpenAIError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.services.embedding_service import embed_text


def main() -> None:
    deployment_name = settings.embedding_deployment_name
    endpoint = settings.embedding_endpoint

    if not deployment_name:
        raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME is not configured")

    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme not in {"http", "https"}:
        raise ValueError("AZURE_OPENAI_EMBEDDING_ENDPOINT must start with http:// or https://")
    if parsed_endpoint.path.rstrip("/") != "/openai/v1":
        print("WARNING: AZURE_OPENAI_EMBEDDING_ENDPOINT should usually end with /openai/v1/")

    try:
        vector = embed_text("Kiem tra embedding cho ZenTech AI.")
    except OpenAIError as exc:
        print("Embedding smoke test failed")
        print(f"Deployment: {deployment_name}")
        print(f"Error: {exc.__class__.__name__}: {exc}")
        raise SystemExit(1) from exc

    print("Embedding smoke test passed")
    print(f"Deployment: {deployment_name}")
    print(f"Vector dimension: {len(vector)}")
    print(f"Configured Qdrant vector size: {settings.qdrant_vector_size}")

    if len(vector) != settings.qdrant_vector_size:
        print("WARNING: Vector dimension does not match QDRANT_VECTOR_SIZE")


if __name__ == "__main__":
    main()
