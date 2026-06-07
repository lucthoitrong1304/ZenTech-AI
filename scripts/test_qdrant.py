import argparse
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.schemas.rag import QdrantDocument
from app.services.qdrant_tools import ensure_collection, insert_documents, search_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test Qdrant insert and search.")
    parser.add_argument(
        "--content",
        default="ZenTech co ho tro tu van chung ve bao hanh, giao hang, thanh toan va doi tra.",
        help="Document content to insert into Qdrant.",
    )
    parser.add_argument(
        "--query",
        default="ZenTech ho tro nhung van de nao?",
        help="Search query to test against Qdrant.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not settings.qdrant_url:
        raise ValueError("QDRANT_URL is not configured")
    if not settings.embedding_deployment_name:
        raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME is not configured")

    document_id = str(uuid4())
    source = "smoke-test:qdrant"

    print("Qdrant smoke test started")
    print(f"Collection: {settings.qdrant_collection_name}")
    print(f"Vector size: {settings.qdrant_vector_size}")
    print(f"Embedding deployment: {settings.embedding_deployment_name}")

    ensure_collection()
    insert_documents(
        [
            QdrantDocument(
                id=document_id,
                content=args.content,
                source=source,
                metadata={"test": True},
            )
        ]
    )

    results = search_documents(args.query, limit=3)
    print(f"Inserted document id: {document_id}")
    print(f"Search result count: {len(results)}")

    if not results:
        print("Qdrant smoke test failed: no search results returned")
        raise SystemExit(1)

    top_result = results[0]
    print("Qdrant smoke test passed")
    print(f"Top result id: {top_result.id}")
    print(f"Top result score: {top_result.score}")
    print(f"Top result source: {top_result.source}")


if __name__ == "__main__":
    main()
