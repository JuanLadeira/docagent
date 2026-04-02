"""
Setup SQLAlchemy async para o DocAgent.

DATABASE_URL via .env:
  DOCAGENT_DB_URL=postgresql+asyncpg://user:pass@localhost/docagent
  DOCAGENT_DB_URL=sqlite+aiosqlite:///./docagent.db  (padrao dev)
"""
from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

from docagent.settings import Settings

settings = Settings()


class Base(DeclarativeBase):
    """Base class para todos os modelos SQLAlchemy do DocAgent."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )


engine = create_async_engine(
    settings.DOCAGENT_DB_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — injeta sessao async por request."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session


AsyncDBSession = Annotated[AsyncSession, Depends(get_db)]
