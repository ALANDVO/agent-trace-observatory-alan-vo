"""Application configuration and environment settings."""

import os
from typing import List, Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration loaded from environment."""

    project_name: str = "Agent Trace Observatory"
    project_slug: str = "agent-trace-observatory-alan-vo"
    version: str = "1.0.0"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    demo_mode: bool = Field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes"))
    host: str = Field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-key-32-chars-minimum-length-needed"))
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/traces.db"))

    # Allowed CORS origins
    frontend_origin: str = Field(default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173"))

    # LLM Settings (LLM_API_KEY is the only secret)
    llm_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LLM_API_KEY") or None)
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai-compatible"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen3.8-27b"))
    llm_base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://llm.chris-vo.com/v1"))
    llm_timeout_seconds: float = Field(default=15.0)

    # Keycloak OIDC Settings
    oidc_issuer_url: str = Field(default_factory=lambda: os.getenv("OIDC_ISSUER_URL", "http://127.0.0.1:8080/realms/agent-observatory"))
    oidc_client_id: str = Field(default_factory=lambda: os.getenv("OIDC_CLIENT_ID", "agent-trace-observatory"))
    oidc_client_secret: Optional[str] = Field(default_factory=lambda: os.getenv("OIDC_CLIENT_SECRET") or None)
    oidc_redirect_uri: str = Field(default_factory=lambda: os.getenv("OIDC_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/callback"))
    oidc_audience: str = Field(default_factory=lambda: os.getenv("OIDC_AUDIENCE", "agent-trace-observatory"))

    def validate_environment(self) -> None:
        """Enforce production security constraints: startup REFUSES demo mode in production."""
        if self.environment == "production" and self.demo_mode:
            raise RuntimeError(
                "CRITICAL SECURITY FAILURE: Demo mode is strictly forbidden in production environments! "
                "Set DEMO_MODE=false or change ENVIRONMENT to development/local."
            )
        if self.demo_mode and self.host not in ("127.0.0.1", "localhost", "0.0.0.0"):
            raise RuntimeError(
                f"Demo mode can only bind to loopback addresses, current host is {self.host}."
            )


settings = Settings()
settings.validate_environment()
