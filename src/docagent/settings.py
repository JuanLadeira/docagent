"""
Configuracoes da aplicacao via variaveis de ambiente.
"""
import os


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "insecure-dev-key-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    DOCAGENT_DB_URL: str = os.getenv(
        "DOCAGENT_DB_URL", "sqlite+aiosqlite:///./docagent.db"
    )
    ADMIN_DEFAULT_USERNAME: str = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
    ADMIN_DEFAULT_PASSWORD: str = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin")
    EVOLUTION_API_URL: str = os.getenv("EVOLUTION_API_URL", "http://evolution-api:8080")
    EVOLUTION_API_KEY: str = os.getenv("EVOLUTION_API_KEY", "")
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "http://api:8000")

    # Áudio — system defaults (usados quando não há AudioConfig no banco)
    AUDIO_STT_HABILITADO: bool = os.getenv("AUDIO_STT_HABILITADO", "false").lower() == "true"
    AUDIO_STT_PROVIDER: str = os.getenv("AUDIO_STT_PROVIDER", "faster_whisper")
    AUDIO_STT_MODELO: str = os.getenv("AUDIO_STT_MODELO", "base")
    AUDIO_TTS_HABILITADO: bool = os.getenv("AUDIO_TTS_HABILITADO", "false").lower() == "true"
    AUDIO_TTS_PROVIDER: str = os.getenv("AUDIO_TTS_PROVIDER", "piper")
    AUDIO_MODO_RESPOSTA: str = os.getenv("AUDIO_MODO_RESPOSTA", "audio_e_texto")
    # Chave Fernet para criptografar elevenlabs_api_key (base64url de 32 bytes).
    # Se vazia, salva plaintext com aviso de log.
    AUDIO_FERNET_KEY: str = os.getenv("AUDIO_FERNET_KEY", "")

    # HuggingFace Local / TurboQuant (provider hf_local)
    # Requer: uv sync --extra hf  (instala torch, transformers, turboquant-torch)
    # ATENÇÃO: usar --workers 1 no uvicorn para não duplicar o modelo na VRAM
    LLM_HF_MODEL: str = os.getenv("LLM_HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    TURBOQUANT_ENABLED: bool = os.getenv("TURBOQUANT_ENABLED", "true").lower() == "true"
    TURBOQUANT_BITS: int = int(os.getenv("TURBOQUANT_BITS", "3"))
    TURBOQUANT_DEVICE: str = os.getenv("TURBOQUANT_DEVICE", "cuda")
