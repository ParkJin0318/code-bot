"""Application configuration using Pydantic Settings v2."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    llm_api_key: str
    llm_base_url: str
    llm_model: str

    embedding_model: str
    embedding_device: str

    rerank_model: str
    rerank_top_n: int
    rerank_max_length: int
    retrieve_top_k: int

    codebase_path: Path
    collection_name: str
    chroma_db_path: Path

    api_host: str
    api_port: int
    api_reload: bool

    log_level: str

    atlassian_gateway_url: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
