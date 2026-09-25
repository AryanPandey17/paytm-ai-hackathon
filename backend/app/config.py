"""Central settings. Reads ../.env (repo root) then ./.env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT / ".env"), str(BACKEND / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_env: str = "dev"
    frontend_origin: str = "http://localhost:5173"
    public_backend_url: str = "http://localhost:8000"
    db_path: str = str(BACKEND / "data" / "commerceos.db")
    audio_cache_dir: str = str(ROOT / "demo" / "audio")

    # --- LLM fallback chain (comma separated, tried in order) ---
    llm_provider_order: str = "sarvam,gemini,groq,openrouter,openai,rules"
    llm_timeout_s: float = 25.0
    llm_cooldown_s: int = 300  # how long an exhausted provider is skipped

    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_chat_model: str = "sarvam-105b"
    sarvam_stt_model: str = "saaras:v3"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "shubh"
    sarvam_translate_model: str = "mayura:v1"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Memory (Cognee) ---
    memory_backend: str = "local"  # local | cognee
    cognee_llm_api_key: str = ""

    # --- n8n ---
    n8n_base_url: str = ""  # e.g. https://your-n8n.app.n8n.cloud
    n8n_webhook_secret: str = "change-me"
    n8n_path_udhaar: str = "/webhook/udhaar-nudge"
    n8n_path_capital: str = "/webhook/capital-offer"
    n8n_path_escalation: str = "/webhook/onboarding-escalation"
    n8n_path_send: str = "/webhook/whatsapp-send"
    n8n_path_po: str = "/webhook/bazaar-po"

    # --- Guardrails ---
    capital_approval_threshold: int = 25000
    resolver_confidence_threshold: float = 0.7
    nudge_cooldown_days: int = 3

    # --- Demo phone numbers (WhatsApp test recipients, E.164 without +) ---
    demo_merchant_phone: str = "919800000001"
    demo_customer_phone: str = "919800000002"
    demo_ops_phone: str = "919800000003"


settings = Settings()
