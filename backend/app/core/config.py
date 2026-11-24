"""
core/config.py — Application settings loaded from environment variables.
Never commit .env; use .env.example as the template.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # ── MongoDB ──────────────────────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "pragyan_ppi"
    mongodb_test_db: str = "ppi_test"
    log_level: str = "INFO"

    # ── Application identity ─────────────────────────────────────────────────
    app_name: str = "Pragyan Plant Intelligence"
    app_version: str = "0.4.0"

    # ── Data roots ───────────────────────────────────────────────────────────
    data_root: str = "../Data"
    manifests_root: str = "../Data/manifests"
    derived_ocr_root: str = "../Data/derived/ocr"

    # ── OpenAI (chat + embeddings) ───────────────────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # Must equal qdrant_vector_size; text-embedding-3 models support reduced dimensions.
    openai_embedding_dimensions: int = 1024
    openai_temperature: float = 0.1

    # ── Qdrant (Docker) ──────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "pragyan_evidence_v1"
    qdrant_vector_size: int = 1024

    # ── Neo4j (Docker) ───────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "local_secret_only"
    neo4j_database: str = "neo4j"

    # ── RAG feature flags ────────────────────────────────────────────────────
    rag_vector_enabled: bool = True
    rag_graph_enabled: bool = True
    rag_allow_external_llm: bool = False

    # ── Retrieval configuration ──────────────────────────────────────────────
    rag_max_chunks: int = 10
    rag_vector_top_k: int = 15
    rag_score_threshold: float = 0.30
    rag_graph_max_hops: int = 2


settings = Settings()
