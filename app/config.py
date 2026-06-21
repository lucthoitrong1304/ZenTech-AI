from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and ..env."""

    azure_openai_api_key: str = Field(alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_model_name: str | None = Field(default=None, alias="AZURE_OPENAI_MODEL_NAME")
    azure_openai_chat_deployment_name: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
    )
    azure_openai_embedding_model_name: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_EMBEDDING_MODEL_NAME",
    )
    azure_openai_embedding_deployment_name: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
    )
    azure_openai_embedding_endpoint: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_EMBEDDING_ENDPOINT",
    )

    azure_openai_vision_model_name: str = Field(
        default="gpt-5.4-mini",
        alias="AZURE_OPENAI_VISION_MODEL_NAME",
    )

    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(
        default="zentech_knowledge",
        alias="QDRANT_COLLECTION_NAME",
    )
    qdrant_knowledge_collection: str = Field(
        default="knowledge_vectors",
        alias="QDRANT_KNOWLEDGE_COLLECTION",
    )
    qdrant_product_collection: str = Field(
        default="product_vectors",
        alias="QDRANT_PRODUCT_COLLECTION",
    )
    qdrant_vector_size: int = Field(default=1536, alias="QDRANT_VECTOR_SIZE")
    qdrant_search_limit: int = Field(default=5, alias="QDRANT_SEARCH_LIMIT")

    spring_boot_internal_url: str = Field(
        default="http://localhost:8080",
        alias="SPRING_BOOT_INTERNAL_URL",
    )
    spring_boot_internal_token: str = Field(
        default="zentech_internal_secret_token_123!@",
        alias="SPRING_BOOT_INTERNAL_TOKEN",
    )

    @property
    def chat_deployment_name(self) -> str:
        deployment_name = self.azure_openai_chat_deployment_name or self.azure_openai_model_name
        if not deployment_name:
            raise ValueError("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME is not configured")
        return deployment_name

    @property
    def embedding_deployment_name(self) -> str | None:
        return self.azure_openai_embedding_deployment_name or self.azure_openai_embedding_model_name

    @property
    def embedding_endpoint(self) -> str:
        return self.azure_openai_embedding_endpoint or self.azure_openai_endpoint

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
