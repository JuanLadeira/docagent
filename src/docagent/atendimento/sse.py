import asyncio
from collections import defaultdict


class AtendimentoSseManager:
    def __init__(self):
        self._queues: dict[int, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, atendimento_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[atendimento_id].append(q)
        return q

    def unsubscribe(self, atendimento_id: int, queue: asyncio.Queue) -> None:
        if queue in self._queues[atendimento_id]:
            self._queues[atendimento_id].remove(queue)

    async def broadcast(self, atendimento_id: int, event: dict) -> None:
        for q in list(self._queues[atendimento_id]):
            await q.put(event)


class AtendimentoListaSseManager:
    """Broadcast tenant-nível para atualizar a lista de atendimentos em tempo real."""

    def __init__(self):
        self._queues: dict[int, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, tenant_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[tenant_id].append(q)
        return q

    def unsubscribe(self, tenant_id: int, queue: asyncio.Queue) -> None:
        if queue in self._queues[tenant_id]:
            self._queues[tenant_id].remove(queue)

    async def broadcast(self, tenant_id: int, event: dict) -> None:
        for q in list(self._queues[tenant_id]):
            await q.put(event)


atendimento_sse_manager = AtendimentoSseManager()
atendimento_lista_sse_manager = AtendimentoListaSseManager()
