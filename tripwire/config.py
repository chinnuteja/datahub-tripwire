"""Environment-only configuration with safe local defaults."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TripwireSettings(BaseSettings):
    """Validated settings shared by the CLI and application services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TRIPWIRE_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "local"
    artifact_dir: Path = Path("artifacts/runtime")
    demo_dir: Path = Path("demo/fraud")
    datahub_gms_url: str = "http://localhost:8080"
    datahub_frontend_url: str = "http://localhost:9002"
    datahub_token: SecretStr | None = None
    mcp_command: str = Field(default_factory=lambda: sys.executable)
    mcp_args: tuple[str, ...] = ("-m", "mcp_server_datahub")
    mcp_timeout_seconds: float = Field(default=30, gt=0, le=180)

    @field_validator("datahub_gms_url", "datahub_frontend_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("DataHub URLs must use http or https")
        return value.rstrip("/")

    def ensure_runtime_directories(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> TripwireSettings:
    """Load settings at command execution time, never at import time."""

    return TripwireSettings()
