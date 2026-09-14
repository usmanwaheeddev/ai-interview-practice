from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hiring"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str = "http://localhost:9000"
    # Used only to *construct and sign* presigned URLs — the browser calling
    # them can't resolve the internal docker-compose hostname `minio`, so
    # this must be the address the browser can actually reach. Same MinIO,
    # different address for two different callers (backend vs. browser).
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "hiring-interview"
    s3_region: str = "us-east-1"

    jwt_secret: str = "dev-only-change-me-this-must-be-at-least-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    cors_origins: list[str] = ["http://localhost:5173"]

    # Provider selection — see architecture.md §7
    llm_provider: str = "fake"
    stt_provider: str = "fake"
    # STT_PROVIDER remains the broad provider switch (including "fake").
    # STT_ENGINE selects the concrete local Whisper implementation.
    stt_engine: str = "faster_whisper"
    tts_provider: str = "fake"
    storage_provider: str = "s3"

    # Self-hosted provider config — memory.md ADR-014
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"

    # Cloud free-tier LLM — memory.md ADR-017. No default key: the app must
    # not silently start with an empty credential against a real API.
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    # Multilingual (English/Hindi/Urdu) — "tiny"/"base" multilingual quality
    # is noticeably worse than English-only "tiny.en" was, which first moved
    # this up to "small". Moved back down to "base" since: on this app's
    # actual (shared, CPU-only, 4-core) host, "small" was slow enough that
    # transcription calls routinely blew past even a 30s timeout under any
    # concurrent host load, and a timed-out call's CPU-bound worker thread
    # can't actually be cancelled (see faster_whisper.py's transcribe()) —
    # so a slow model doesn't just mean one slow answer, it means a stuck
    # thread that keeps competing with every later call forever. "base" is
    # a real accuracy trade-off for Hindi/Urdu, but a session that always
    # times out has no accuracy at all.
    whisper_model_size: str = "base"
    # Optional engine-neutral model label. The legacy WHISPER_MODEL_SIZE
    # remains authoritative for faster-whisper when this is unset.
    stt_model_size: str | None = None
    # Native faster-whisper tuning. Four CPU threads lets the English
    # small.en model stay comfortably ahead of real-time input on the
    # development Mac; greedy decoding avoids paying the beam-search cost
    # for negligible accuracy benefit in conversational English.
    whisper_cpu_threads: int = 4
    whisper_beam_size: int = 1
    whisper_segment_timeout_s: float = 60.0
    whisper_cpp_binary_path: str = ""
    whisper_cpp_model_path: str = ""
    whisper_cpp_threads: int = 4
    piper_voice: str = "en_US-lessac-medium"
    # Piper ships no Urdu voice — the Urdu path in PiperTTSProvider falls
    # back to espeak-ng instead of a downloaded voice model.
    piper_voice_hi: str = "hi_IN-pratham-medium"
    piper_voices_dir: str = "/opt/piper-voices"

    # Coding-challenge execution sandbox — Phase 1 of the coding-challenge
    # feature. See docker-compose.yml's `piston` service and
    # Makefile's `piston-setup` target for the package install step.
    execution_provider: str = "fake"
    piston_base_url: str = "http://localhost:2000"
    piston_compile_timeout_ms: int = 10000
    piston_run_timeout_ms: int = 10000
    piston_compile_memory_limit_bytes: int = 256 * 1024 * 1024
    piston_run_memory_limit_bytes: int = 256 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
