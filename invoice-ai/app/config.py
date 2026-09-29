"""Service configuration via pydantic-settings (BaseSettings).

Never read ``os.environ`` directly anywhere else in the app — this module is
the single config seam (mirrors how the Odoo addon pins the model id and
timeout in exactly one place, ``llm_service.py``).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": the monorepo root .env (compose vars like POSTGRES_DB,
    # DOMAIN) is picked up by pydantic-settings auto-load; unknown keys must
    # never break the service.
    model_config = SettingsConfigDict(
        env_prefix="INVOICE_AI_",
        env_file=".env",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    anthropic_max_tokens: int = 2048
    anthropic_timeout_seconds: float = 90.0
    anthropic_max_retries: int = 2

    # Voyage AI — embeddings (v0.10). Anthropic ships no embedding model, so
    # vendor-doc retrieval uses voyage-3 (1024-dim). Key comes from .env /
    # INVOICE_AI_VOYAGE_API_KEY.
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"
    voyage_dimensions: int = 1024

    database_url: str = ""

    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MiB — matches docs/openapi.yaml
    ocr_render_dpi: int = 300

    # JWT auth (app/auth.py). The shared secret is distributed out-of-band
    # to the Odoo side via ir.config_parameter (invoice_agent.jwt_secret).
    # audience is a claim that must match on both sides — a token minted
    # with the right secret but wrong aud is rejected.
    jwt_secret: str = ""
    jwt_audience: str = "invoice-ai"
    jwt_ttl_seconds: int = 60

    # --- Result delivery (worker -> Odoo) --------------------------------
    # Results used to be published to the ``invoice.result`` AMQP queue, which
    # Odoo drained with a per-process daemon thread. Odoo now exposes an HTTP
    # webhook (``POST /invoice_agent/result``) and the worker posts the signed
    # JWT there instead — review finding P1-3 / Wave 3. The Odoo base URL is
    # therefore the one new piece of configuration, and it is the mirror of the
    # Odoo-side ``INVOICE_AI_LLM_SERVICE_URL``.
    odoo_base_url: str = "http://odoo:8069"
    odoo_result_path: str = "/invoice_agent/result"
    odoo_result_timeout_seconds: float = 30.0


settings = Settings()
