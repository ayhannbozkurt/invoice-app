"""Application settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: Literal["openai", "ollama"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    ocr_lang: str = "en"
    ocr_max_retries: int = 3
    ocr_retry_delay: float = 1.0
    ocr_providers: list = ["paddleocr", "easyocr"]
    easyocr_langs: list = ["en", "tr"]

    agent_timeout: int = 30
    parallel_llm_enabled: bool = True
    min_confidence_threshold: float = 0.7

    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    data_dir: str = "data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis_url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
