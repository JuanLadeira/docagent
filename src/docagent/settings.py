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
