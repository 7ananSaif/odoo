"""Typed application settings loaded from the environment (.env)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Values come from `.env` / real env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Manager web app ---------------------------------------------------
    secret_key: str = Field(default="change-me-session-signing-key")
    owner_email: str = Field(default="owner@example.com")
    owner_name: str = Field(default="SaaS Owner")
    session_cookie: str = Field(default="saas_session")
    session_max_age_minutes: int = Field(default=720)

    # --- Manager database --------------------------------------------------
    manager_db_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/saas_manager"
    )

    # --- Encryption --------------------------------------------------------
    secrets_key: str = Field(default="")

    # --- Odoo --------------------------------------------------------------
    odoo_base_url: str = Field(default="https://app.example.com")
    odoo_domain: str = Field(default="example.com")
    odoo_master_password: str = Field(default="")
    odoo_manager_token: str = Field(default="")
    odoo_bin: str = Field(default="")
    odoo_python: str = Field(default="")
    odoo_data_dir: str = Field(default="")
    odoo_request_timeout: int = Field(default=60)
    # Browser-reachable base URL of the Odoo server.  The manager itself talks
    # to ``odoo_base_url`` (e.g. http://odoo-control:8069 on the compose
    # network), but a browser cannot resolve that host.  Auto-login links
    # therefore use this URL when set (e.g. http://127.0.0.1:8069 in local dev);
    # when empty they fall back to the per-subdomain public URL.
    odoo_public_url: str = Field(default="")

    # --- PostgreSQL tools --------------------------------------------------
    pg_dump: str = Field(default="pg_dump")
    pg_restore: str = Field(default="pg_restore")
    pg_psql: str = Field(default="psql")
    pg_host: str = Field(default="127.0.0.1")
    pg_port: int = Field(default=5432)
    pg_user: str = Field(default="odoo")
    pg_password: str = Field(default="")
    backup_dir: str = Field(default="backups")

    # --- Workers -----------------------------------------------------------
    celery_broker_url: str = Field(default="redis://127.0.0.1:6379/0")
    celery_result_backend: str = Field(default="redis://127.0.0.1:6379/1")
    update_max_parallel: int = Field(default=2)
    scheduler_enabled: bool = Field(default=True)

    # --- Behaviour ---------------------------------------------------------
    grace_days: int = Field(default=7)
    trial_days: int = Field(default=14)
    default_currency: str = Field(default="USD")
    default_tax_rate: float = Field(default=0.0)
    rate_limit_login: str = Field(default="10/minute")

    # --- Outgoing email (invoice sending, dunning reminders) ---------------
    email_enabled: bool = Field(default=False)
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_use_tls: bool = Field(default=True)
    smtp_use_ssl: bool = Field(default=False)
    email_from: str = Field(default="billing@example.com")
    email_from_name: str = Field(default="SaaS Manager Billing")
    email_timeout: int = Field(default=20)

    @property
    def email_configured(self) -> bool:
        """True when enough SMTP settings are present to send mail."""
        return bool(self.email_enabled and self.smtp_host and self.email_from)

    # --- Derived helpers ---------------------------------------------------
    @property
    def is_configured(self) -> bool:
        """True once the operator filled in the essentials."""
        return bool(self.secrets_key and self.odoo_manager_token)

    @property
    def odoo_browser_base(self) -> str:
        """Base URL a *browser* uses to reach Odoo (falls back to the internal one)."""
        return (self.odoo_public_url or self.odoo_base_url).rstrip("/")

    def tenant_url(self, subdomain: str) -> str:
        """Public URL of a tenant given its subdomain."""
        return f"https://{subdomain}.{self.odoo_domain}"

    def tenant_browser_url(self, subdomain: str, db_name: str) -> str:
        """Browser URL that opens a tenant's Odoo.

        Prefers the explicit ``ODOO_PUBLIC_URL`` (one server, ``?db=`` selects
        the database); otherwise the per-subdomain public URL is used.
        """
        if self.odoo_public_url:
            return f"{self.odoo_browser_base}/web?db={db_name}"
        return f"{self.tenant_url(subdomain)}/web"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


settings = get_settings()
