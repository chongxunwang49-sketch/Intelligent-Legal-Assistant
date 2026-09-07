# -*- coding: utf-8 -*-
"""
智法通 V2 —— 全局配置（pydantic-settings）

所有环境变量统一 ZHIFATONG_ 前缀；本地开发读取 backend/.env，
容器内通过环境变量注入（docker-compose.yml，M8）。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ZHIFATONG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 应用 ----------
    APP_NAME: str = "智法通 V2"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api/v1"

    # ---------- MySQL ----------
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 13306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "zhifatong_root_2026"
    MYSQL_DATABASE: str = "zhifatong"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    # ---------- Redis ----------
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 26379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_POOL_SIZE: int = 10

    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ---------- Neo4j ----------
    NEO4J_ENABLED: bool = True
    NEO4J_URI: str = "bolt://127.0.0.1:17687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "zhifatong_neo4j_2026"
    NEO4J_MAX_QUERY_NODES: int = 80
    NEO4J_DATABASE: str = "neo4j"

    # ---------- JWT ----------
    JWT_SECRET_KEY: str = "zhifatong-v2-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------- Ollama ----------
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_EMBEDDING_MODEL: str = "quentinz/bge-large-zh-v1.5:latest"
    OLLAMA_EMBEDDING_DIM: int = 1024
    OLLAMA_TIMEOUT: int = 120
    OLLAMA_MAX_TOKENS: int = 4096
    OLLAMA_TEMPERATURE: float = 0.7

    # ---------- Rerank（自建精排服务）----------
    RERANK_SERVICE_URL: str = "http://127.0.0.1:9999"
    RERANK_TIMEOUT: int = 30
    RERANK_TOP_N: int = 5

    # ---------- Chroma 向量库 ----------
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "zhifatong_legal_v2"
    CHROMA_EMBEDDING_DIM: int = 1024

    # ---------- 上传 ----------
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: str = "pdf,docx,doc,txt"
    ALLOWED_UPLOAD_EXTENSIONS: str = "pdf,doc,docx,txt,png,jpg,jpeg"

    # ---------- RAG ----------
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5
    RAG_RECALL_TOP_K: int = 20
    RAG_RRF_K: int = 60
    RAG_SIMILARITY_THRESHOLD: float = 0.7
    # Self-RAG
    RAG_RERETRIEVAL_MAX_RETRIES: int = 2
    RAG_RERETRIEVAL_CONFIDENCE_THRESHOLD: float = 0.6

    # ---------- 安全 ----------
    LOGIN_FAIL_MAX_ATTEMPTS: int = 5
    LOGIN_FAIL_TTL_SECONDS: int = 1800

    # ---------- 合同审查 ----------
    CONTRACT_REVIEW_HIGH_RISK_THRESHOLD: int = 80

    # ---------- 额度 ----------
    QUOTA_QA_DAILY: int = 50
    QUOTA_CONTRACT_DAILY: int = 10

    # ---------- 通知/数据 ----------
    WELCOME_NOTIFICATION: bool = True
    MAX_CONVERSATIONS_PER_USER: int = 200

    # ---------- LangSmith（配置即启用，默认关闭）----------
    LANGSMITH_TRACING_ENABLED: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT_NAME: str = "zhifatong-v2"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    # ---------- CORS ----------
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:8188",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8188",
        "http://localhost:8080",
        "http://localhost:80",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
