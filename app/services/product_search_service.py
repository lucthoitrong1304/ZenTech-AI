import logging
import re
import unicodedata
from qdrant_client import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.services.embedding_service import embed_text
from app.services.qdrant_client import build_qdrant_client

logger = logging.getLogger("ai-service")


CATEGORY_MAPPING = {
    "chargers": "Chargers",
    "charger": "Chargers",
    "sac": "Chargers",
    "thiet bi sac": "Chargers",
    "cu sac": "Chargers",
    "ban phim": "Hall Effect Keyboard",
    "keyboard": "Hall Effect Keyboard",
    "keyboards": "Hall Effect Keyboard",
    "hall effect keyboard": "Hall Effect Keyboard",
    "he keyboard": "Hall Effect Keyboard",
    "chuot": "Mice",
    "mouse": "Mice",
    "mice": "Mice",
    "loa": "Speakers",
    "speaker": "Speakers",
    "speakers": "Speakers",
    "tai nghe": "Earbuds",
    "earbuds": "Earbuds",
    "earbud": "Earbuds",
    "phu kien": "Accessories",
    "accessories": "Accessories",
}


def normalize_search_text(value: str) -> str:
    no_marks = "".join(
        char for char in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", no_marks).split())


def filter_explicit_product_matches(query: str, candidates: list[dict]) -> list[dict]:
    normalized_query = normalize_search_text(query)
    matches = []

    for candidate in candidates:
        normalized_name = normalize_search_text(str(candidate.get("name") or ""))
        if normalized_name and normalized_name in normalized_query:
            matches.append((normalized_name, candidate))

    if not matches:
        return candidates

    longest_length = max(len(name) for name, _ in matches)
    return [candidate for name, candidate in matches if len(name) == longest_length]

def normalize_category_name(name: str | None) -> str | None:
    if not name:
        return None
    import unicodedata
    name = name.replace("Đ", "D").replace("đ", "d")
    no_marks = "".join(
        char for char in unicodedata.normalize("NFD", name.lower())
        if unicodedata.category(char) != "Mn"
    )
    cleaned = " ".join(no_marks.strip().split())
    return CATEGORY_MAPPING.get(cleaned, None)


def search_product_candidates(query: str, limit: int = 5, category_name: str | None = None) -> list[dict]:
    clean_query = query.strip()
    if not clean_query:
        return []
    if not settings.qdrant_url or not settings.embedding_deployment_name:
        return []

    client = build_qdrant_client()
    col_name = settings.qdrant_product_collection

    try:
        if not client.collection_exists(collection_name=col_name):
            logger.warning(f"Qdrant collection {col_name} does not exist.")
            return []
    except UnexpectedResponse as ex:
        logger.error(f"Error checking Qdrant collection: {str(ex)}")
        return []

    # Always filter for status == ACTIVE for product searches
    must_conditions = [
        models.FieldCondition(
            key="status",
            match=models.MatchValue(value="ACTIVE"),
        )
    ]
    
    norm_cat = normalize_category_name(category_name)
    if norm_cat:
        logger.info(f"Filtering product search by categoryName: '{norm_cat}'")
        must_conditions.append(
            models.FieldCondition(
                key="categoryName",
                match=models.MatchValue(value=norm_cat),
            )
        )

    query_filter = models.Filter(must=must_conditions)

    try:
        response = client.query_points(
            collection_name=col_name,
            query=embed_text(clean_query),
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )

        candidates = []
        if response.points:
            top_score = float(response.points[0].score)
            margin = 0.08
            min_threshold = 0.35
            
            for point in response.points:
                score = float(point.score)
                if score < (top_score - margin) or score < min_threshold:
                    continue
                
                payload = point.payload or {}
                candidates.append({
                    "id": point.id,
                    "score": score,
                    "productId": payload.get("productId"),
                    "variantId": payload.get("variantId"),
                    "sku": payload.get("sku"),
                    "name": payload.get("name"),
                    "searchText": payload.get("searchText"),
                    "categoryId": payload.get("categoryId"),
                    "categoryName": payload.get("categoryName"),
                    "brandId": payload.get("brandId"),
                    "brandName": payload.get("brandName"),
                    "colors": payload.get("colors", []),
                    "sizes": payload.get("sizes", []),
                    "material": payload.get("material"),
                    "tags": payload.get("tags", []),
                    "imageKeys": payload.get("imageKeys", []),
                    "updatedAt": payload.get("updatedAt"),
                })
        logger.info(f"Retrieved {len(candidates)} product candidates from Qdrant.")
        return candidates

    except Exception as ex:
        logger.error(f"Failed to query product_vectors from Qdrant: {str(ex)}")
        return []
