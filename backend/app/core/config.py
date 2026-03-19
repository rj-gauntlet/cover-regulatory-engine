from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://cover:cover@localhost:5432/cover"
    database_url_sync: str = "postgresql://cover:cover@localhost:5432/cover"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    mapbox_access_token: str = ""

    zimas_base_url: str = "https://zimas.lacity.org/arcgis/rest/services/zma/zimas/MapServer"

    amlegal_base_url: str = "https://codelibrary.amlegal.com/codes/los_angeles/latest"

    parcel_cache_ttl_days: int = 30
    change_detection_interval_hours: int = 720  # ~monthly

    chunk_size: int = 512
    chunk_overlap: int = 128

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
