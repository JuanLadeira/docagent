from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.database import AsyncDBSession
from docagent.system_config.models import SystemConfig

LLM_MODE_KEY = "llm_mode"
LLM_MODE_LOCAL = "local"
LLM_MODE_API = "api"


class SystemConfigService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: str | None = None) -> str | None:
        result = await self.session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else default

    async def set(self, key: str, value: str | None) -> SystemConfig:
        result = await self.session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            row = SystemConfig(key=key, value=value)
            self.session.add(row)
        await self.session.flush()
        return row

    async def get_llm_mode(self) -> str:
        """Retorna o modo LLM global: 'local' (Ollama) ou 'api' (tenant fornece chave)."""
        return await self.get(LLM_MODE_KEY, LLM_MODE_LOCAL) or LLM_MODE_LOCAL

    async def get_all(self) -> dict[str, str | None]:
        result = await self.session.execute(select(SystemConfig))
        rows = result.scalars().all()
        return {r.key: r.value for r in rows}


def get_system_config_service(session: AsyncDBSession) -> SystemConfigService:
    return SystemConfigService(session)


SystemConfigServiceDep = Annotated[SystemConfigService, Depends(get_system_config_service)]
