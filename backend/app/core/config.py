"""Configuracao da aplicacao via variaveis de ambiente (metodologia 12-factor)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao tipada, carregada de variaveis de ambiente / arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Geral ---
    project_name: str = "Predicta"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- PostgreSQL (catalogo) ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "forzy"
    postgres_password: str = "forzy_dev_password"
    postgres_db: str = "forzy_catalog"

    # --- TimescaleDB (series temporais) ---
    timescale_host: str = "localhost"
    timescale_port: int = 5434
    timescale_user: str = "forzy"
    timescale_password: str = "forzy_dev_password"
    timescale_db: str = "forzy_timeseries"

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379

    # --- MQTT ---
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883

    # --- OPC-UA ---
    opcua_endpoint: str = "opc.tcp://localhost:4840/forzy/server/"
    opcua_namespace_uri: str = "http://forzy.promon/opcua/"
    opcua_publishing_interval_ms: int = 1000

    # --- ChromaDB ---
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # --- Seguranca ---
    jwt_secret_key: str = "dev-only-secret-change-me-in-production-min32b"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # --- LLM (chat de troubleshooting com RAG) ---
    llm_provider: str = "anthropic"
    llm_model: str = "claude-3-5-haiku-20241022"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- RAG (recuperacao aumentada para o chat) ---
    rag_vector_backend: str = "memory"  # "memory" | "chroma"
    rag_documents_dir: str = "/rag/documents"
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 150
    rag_top_k: int = 4
    rag_embedding_dim: int = 384

    # --- RBAC (controle de acesso baseado em papeis) ---
    rbac_enabled: bool = True

    # --- Feature flags (modularidade) ---
    feature_auth: bool = True
    feature_assets: bool = True
    feature_telemetry: bool = True
    feature_vision: bool = True
    feature_ml: bool = True
    feature_alerts: bool = True
    feature_rag: bool = True
    feature_automation: bool = True
    feature_governance: bool = True

    @property
    def catalog_database_url(self) -> str:
        """URL assincrona (asyncpg) do banco de catalogo."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def timeseries_database_url(self) -> str:
        """URL assincrona (asyncpg) do banco de series temporais."""
        return (
            f"postgresql+asyncpg://{self.timescale_user}:{self.timescale_password}"
            f"@{self.timescale_host}:{self.timescale_port}/{self.timescale_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devolve a instancia unica (cacheada) de Settings."""
    return Settings()
