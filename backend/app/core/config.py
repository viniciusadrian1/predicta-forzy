"""Configuracao da aplicacao via variaveis de ambiente (metodologia 12-factor)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_asyncpg(url: str) -> str:
    """Normaliza uma URL de Postgres para o driver asyncpg, sem querystring.

    Aceita ``postgres://`` / ``postgresql://`` (Neon, Supabase, Heroku) e
    descarta ``?sslmode=...`` (o SSL e tratado via connect_args).
    """
    url = url.split("?", 1)[0]
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    """Configuracao tipada, carregada de variaveis de ambiente / arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Geral ---
    project_name: str = "Predicta"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- Banco externo unico (Neon/Supabase): sobrepoe catalogo E telemetria ---
    # Se definido, catalogo e telemetria usam o MESMO Postgres externo (com SSL).
    # Vazio = usa as variaveis POSTGRES_*/TIMESCALE_* abaixo (Docker local).
    database_url: str = ""

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
    # URL base do frontend (links clicaveis do PDF inteligente). Vazio = usa a
    # 1a origem de CORS; util quando front e API tem dominios diferentes.
    frontend_base_url: str = ""

    # --- LLM (chat de troubleshooting com RAG) ---
    # provider "openai" | "anthropic". Sem a chave do provider, o chat cai no
    # modo offline (resposta extrativa a partir da base recuperada).
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
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

    # --- Sensores fisicos Forzy (API HTTP externa) ---
    # URL do tunel divulgado pela Forzy (efemera - ajustar quando mudar).
    # Vazio = ingestao externa desabilitada.
    external_sensors_base_url: str = ""
    # Mapeamento "TAG:endpoint" separado por virgula.
    external_sensors_map: str = "MTR-F01:/get_s1,MTR-F02:/get_s2"
    external_sensors_poll_seconds: float = 30.0

    # --- Simulador de demo (deploy publico sem OPC-UA) ---
    # Gera telemetria recente para os 3 motores (MTR-001 fisico + replay real
    # de MTR-F01/F02) para os cards ficarem "AO VIVO" e os graficos preenchidos.
    # Desligado localmente (o docker-compose usa o simulador OPC-UA real).
    demo_simulator: bool = False
    demo_simulator_interval_seconds: float = 12.0
    demo_simulator_load: float = 0.75  # carga do MTR-001 (0..1)
    demo_history_csv: str = "data/history_forzy_iolink.csv"

    # --- Alertas: ativos avaliados pelo verificador periodico ---
    monitored_asset_tags: str = "MTR-001,MTR-F01,MTR-F02"
    # Webhook para notificar alertas >= WARNING (Teams/Slack/CMMS). Vazio = so grava.
    alert_webhook_url: str = ""
    # Circuit breaker: suspende o alerta automatico quando o dado nao e confiavel.
    # O documento de governanca usa 10s (dados IO-Link de alta frequencia); aqui o
    # padrao e mais folgado por causa da cadencia de poll (30s) + dedup de idle.
    circuit_breaker_gap_seconds: float = 120.0

    # --- Volt (chatbot de manutencao) ---
    # Limiar de confianca: abaixo dele, o diagnostico e escalado a um humano.
    volt_confidence_threshold: float = 0.5
    # Ativos criticos para a producao: sempre exigem revisao humana, mesmo
    # com alta confianca. ponytail: virar campo do ativo quando houver UI.
    volt_critical_asset_tags: str = "MTR-001"

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
    feature_volt: bool = True

    @property
    def catalog_database_url(self) -> str:
        """URL assincrona (asyncpg) do banco de catalogo."""
        if self.database_url:
            return _to_asyncpg(self.database_url)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def timeseries_database_url(self) -> str:
        """URL assincrona (asyncpg) do banco de series temporais.

        Com ``database_url`` definido, usa o MESMO Postgres externo do catalogo
        (as tabelas de telemetria convivem com as do catalogo no mesmo banco).
        """
        if self.database_url:
            return _to_asyncpg(self.database_url)
        return (
            f"postgresql+asyncpg://{self.timescale_user}:{self.timescale_password}"
            f"@{self.timescale_host}:{self.timescale_port}/{self.timescale_db}"
        )

    @property
    def db_connect_args(self) -> dict[str, object]:
        """Args de conexao: exige SSL quando aponta para um Postgres externo."""
        return {"ssl": "require"} if self.database_url else {}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_frontend_base_url(self) -> str:
        """URL do frontend para links do PDF: explicita, 1a origem CORS, ou local."""
        if self.frontend_base_url:
            return self.frontend_base_url.rstrip("/")
        origins = self.cors_origins_list
        return origins[0].rstrip("/") if origins else "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Devolve a instancia unica (cacheada) de Settings."""
    return Settings()
