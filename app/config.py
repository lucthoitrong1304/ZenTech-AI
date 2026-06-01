from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env."""

    azure_openai_api_key: str = Field(alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(alias="AZURE_OPENAI_ENDPOINT")
    # azure_openai_api_version: str = Field(alias="AZURE_OPENAI_API_VERSION")
    azure_openai_deployment_name: str = Field(alias="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_model_name: str = Field(alias="AZURE_OPENAI_MODEL_NAME")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
