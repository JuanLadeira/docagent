from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends

from docagent.settings import Settings


async def get_evolution_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    settings = Settings()
    async with httpx.AsyncClient(
        base_url=settings.EVOLUTION_API_URL,
        headers={"apikey": settings.EVOLUTION_API_KEY},
        timeout=30.0,
    ) as client:
        yield client


EvolutionClientDep = Annotated[httpx.AsyncClient, Depends(get_evolution_client)]
