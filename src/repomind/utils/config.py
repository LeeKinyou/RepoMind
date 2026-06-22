"""Configuration management for RepoMind."""

from pathlib import Path
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "litellm"
    model: str = "claude-sonnet-4-6"
    api_key: str = ""
    base_url: str = ""
    embedding_model: str = "text-embedding-3-small"

class SandboxConfig(BaseModel):
    mode: str = "docker"
    timeout: int = 60

class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    index_dir: str = ".repomind"
    log_level: str = "INFO"
    max_workers: int = 4

def _safe_int(value: str, default: int) -> int:
    """Safely parse integer, returning default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

import functools

@functools.lru_cache(maxsize=1)
def load_config(env_file: str | None = None) -> AppConfig:
    """Load configuration from environment variables and .env file."""
    from dotenv import dotenv_values
    import os

    env_path = Path(env_file) if env_file else Path(".env")
    if env_path.exists():
        values = dotenv_values(env_path)
    else:
        values = {}

    def get(key: str, default: str = "") -> str:
        if key in values:
            val = values[key]
            return val if val is not None else ""
        return os.environ.get(key, default) or default

    return AppConfig(
        llm=LLMConfig(
            provider=get("REPOMIND_LLM_PROVIDER", "litellm"),
            model=get("REPOMIND_LLM_MODEL", "claude-sonnet-4-6"),
            api_key=get("REPOMIND_LLM_API_KEY"),
            base_url=get("REPOMIND_LLM_BASE_URL"),
            embedding_model=get("REPOMIND_EMBEDDING_MODEL", "text-embedding-3-small"),
        ),
        sandbox=SandboxConfig(
            mode=get("REPOMIND_SANDBOX_MODE", "docker"),
            timeout=_safe_int(get("REPOMIND_SANDBOX_TIMEOUT", "60"), 60),
        ),
        index_dir=get("REPOMIND_INDEX_DIR", ".repomind"),
        log_level=get("REPOMIND_LOG_LEVEL", "INFO"),
        max_workers=_safe_int(get("REPOMIND_MAX_WORKERS", "4"), 4),
    )
