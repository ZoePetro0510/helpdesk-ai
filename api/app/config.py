"""Settings, read from environment variables (and a local .env file)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# api/app/config.py -> project root is two levels up (/ inside the container, where /data is mounted)
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://helpdesk:change-me@localhost:5433/helpdesk"

    # LLM: "ollama" (free, local), "anthropic", or "fake" (tests / no model available)
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    anthropic_model: str = "claude-opus-5-5"
    # Effort for Claude: classification is simple, answers need a little more care
    classify_effort: str = "low"
    answer_effort: str = "medium"

    # Embeddings run locally (no API cost)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    kb_dir: Path = _DATA_DIR / "kb"
    eval_file: Path = _DATA_DIR / "eval" / "requests.jsonl"

    # Routing
    top_k: int = 4
    min_retrieval_score: float = 0.55  # below this, skip the answer step: nothing relevant in the KB
    auto_reply_score: float = 0.68  # retrieval score needed to send an answer without a human

    # Tickets: "n8n" sends approved tickets through the n8n workflow, "direct" writes them itself
    ticket_backend: str = "direct"
    n8n_ticket_webhook: str = "http://n8n:5678/webhook/create-ticket"
    public_url: str = "http://localhost:8000"
    # Shared secret between the API and n8n for internal endpoints
    internal_token: str = "change-me-internal"

    # Dashboard assumption: minutes a person would spend answering one routine question
    minutes_per_auto_answer: int = 8

    # Public live demo: shows a banner and limits how fast one visitor can send requests
    demo_mode: bool = False
    demo_requests_per_minute: int = 10
    # Claude prices, USD per million tokens (input, output). Local models cost 0.
    model_prices: dict[str, tuple[float, float]] = {
        "claude-opus-5-5": (4.0, 20.0),
        "claude-sonnet-5-5": (2.0, 10.0),
        "claude-haiku-5-5": (0.10, 0.50),
    }


settings = Settings()
