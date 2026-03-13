from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GTM Copilot API"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    auto_create_schema: bool = True
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/gtm_copilot"
    database_provider: str = "postgresql"  # "postgresql" or "tidb"
    redis_url: str = "redis://localhost:6379/0"

    # TiDB Cloud configuration
    tidb_host: str = ""
    tidb_port: int = 4000
    tidb_user: str = ""
    tidb_password: str = ""
    tidb_database: str = "gtm_copilot"
    tidb_ssl_ca: str = ""  # Path to CA cert for TiDB Cloud

    embedding_dimensions: int = 1536
    retrieval_top_k: int = 8

    openai_base_url: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"

    minimax_api_key: str | None = None
    minimax_group_id: str | None = None
    minimax_base_url: str = "https://api.minimax.io/anthropic"
    minimax_model: str = "MiniMax-M2.5"
    openai_embedding_model: str = "text-embedding-3-small"
    enterprise_mode: bool = False
    security_require_private_llm_endpoint: bool = False
    security_allowed_llm_base_urls: str = ""
    security_fail_closed_on_missing_llm_key: bool = False
    security_fail_closed_on_missing_embedding_key: bool = False
    security_redact_before_llm: bool = True
    security_redact_audit_logs: bool = False
    security_trusted_host_allowlist: str = ""
    security_allow_insecure_http_llm: bool = False

    google_drive_client_id: str | None = None
    google_drive_client_secret: str | None = None
    google_drive_service_account_json: str | None = None
    google_drive_oauth_token_path: str = ".google-drive-token.json"
    google_drive_token_encryption_key: str | None = None
    google_drive_oauth_state_ttl_seconds: int = 600
    google_drive_root_folder_id: str | None = None
    fake_drive_include_github: bool = False
    google_drive_folder_ids: str = ""

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_base_url: str = "https://open.feishu.cn/open-apis"
    feishu_oauth_state_ttl_seconds: int = 600
    feishu_oauth_scopes: str = "offline_access drive:drive:readonly docs:document:readonly"

    call_provider: str = "generic"
    call_api_key: str | None = None
    call_base_url: str | None = None
    # Backward compatibility with legacy env names.
    chorus_api_key: str | None = None
    chorus_base_url: str | None = None

    email_mode: str = "draft"
    internal_domain_allowlist: str = "example.com"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "gtm-copilot@example.com"

    slack_bot_token: str | None = None
    slack_signing_secret: str | None = None
    slack_default_channel: str | None = None

    # MCP integration settings
    salesforce_instance_url: str | None = None
    salesforce_access_token: str | None = None
    zoominfo_api_key: str | None = None
    linkedin_access_token: str | None = None
    firecrawl_api_key: str | None = None
    github_access_token: str | None = None

    # Google OAuth (user login)
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://localhost:8000/api/auth/callback"

    # Observability
    sentry_dsn: str = ""
    log_level: str = "INFO"
    environment: str = "development"

    # JWT settings
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

    @property
    def effective_database_url(self) -> str:
        """Return the database URL based on provider configuration.

        When database_provider is 'tidb' and tidb_host is set, builds a
        mysql+pymysql:// connection string from the TIDB_* settings.
        Otherwise falls back to the DATABASE_URL setting (PostgreSQL default).
        """
        if self.database_provider == "tidb" and self.tidb_host:
            ssl_param = ""
            if self.tidb_ssl_ca:
                ssl_param = f"&ssl_ca={self.tidb_ssl_ca}"
            return (
                f"mysql+pymysql://{self.tidb_user}:{self.tidb_password}"
                f"@{self.tidb_host}:{self.tidb_port}/{self.tidb_database}"
                f"?charset=utf8mb4{ssl_param}"
            )
        return self.database_url

    @property
    def is_tidb(self) -> bool:
        return self.database_provider == "tidb"

    @property
    def drive_folder_ids(self) -> List[str]:
        return [fid.strip() for fid in self.google_drive_folder_ids.split(",") if fid.strip()]

    @property
    def domain_allowlist(self) -> List[str]:
        return [d.strip().lower() for d in self.internal_domain_allowlist.split(",") if d.strip()]

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def trusted_hosts(self) -> List[str]:
        return [h.strip() for h in self.security_trusted_host_allowlist.split(",") if h.strip()]

    @staticmethod
    def normalize_base_url(value: str) -> str:
        parsed = urlparse(value.strip())
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid base URL: {value}")
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    @property
    def allowed_llm_base_urls(self) -> List[str]:
        values = [v.strip() for v in self.security_allowed_llm_base_urls.split(",") if v.strip()]
        normalized: list[str] = []
        for value in values:
            normalized.append(self.normalize_base_url(value))
        return normalized

    def is_allowed_llm_base_url(self, value: str | None) -> bool:
        if not value:
            return False
        allowed = self.allowed_llm_base_urls
        if not allowed:
            return True
        return self.normalize_base_url(value) in set(allowed)


@lru_cache
def get_settings() -> Settings:
    return Settings()
