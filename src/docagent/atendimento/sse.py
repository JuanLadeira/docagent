"""
Fase 13 — SSE managers para atendimentos e lista de atendimentos.
Fase 23 — Suporte a Redis Pub/Sub (bridge pattern) para multi-worker.

Quando redis=None, funciona em modo in-memory (comportamento original).
Quando redis está disponível, broadcast publica no Redis e cada subscriber
tem uma task local que faz o bridge Redis → asyncio.Queue.
"""
import asyncio
import json
from collections import defaultdict


class AtendimentoSseManager:
    def __init__(self, redis=None):
        self._redis = redis
        self._queues: dict[int, list[asyncio.Queue]] = defaultdict(list)
        self._bridge_tasks: dict[asyncio.Queue, asyncio.Task] = {}

    async def subscribe(self, atendimento_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[atendimento_id].append(q)
        if self._redis is not None:
            task = asyncio.create_task(
                self._bridge(f"sse:atendimento:{atendimento_id}", q)
            )
            self._bridge_tasks[q] = task
        return q

    def unsubscribe(self, atendimento_id: int, queue: asyncio.Queue) -> None:
        if queue in self._queues[atendimento_id]:
            self._queues[atendimento_id].remove(queue)
        if task := self._bridge_tasks.pop(queue, None):
            task.cancel()

    async def broadcast(self, atendimento_id: int, event: dict) -> None:
        if self._redis is not None:
            await self._redis.publish(
                f"sse:atendimento:{atendimento_id}", json.dumps(event)
            )
        else:
            for q in list(self._queues[atendimento_id]):
                await q.put(event)

    async def _bridge(self, channel: str, queue: asyncio.Queue) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    await queue.put(json.loads(msg["data"]))
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


class AtendimentoListaSseManager:
    """Broadcast tenant-nível para atualizar a lista de atendimentos em tempo real."""

    def __init__(self, redis=None):
        self._redis = redis
        self._queues: dict[int, list[asyncio.Queue]] = defaultdict(list)
        self._bridge_tasks: dict[asyncio.Queue, asyncio.Task] = {}

    async def subscribe(self, tenant_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[tenant_id].append(q)
        if self._redis is not None:
            task = asyncio.create_task(
                self._bridge(f"sse:lista:{tenant_id}", q)
            )
            self._bridge_tasks[q] = task
        return q

    def unsubscribe(self, tenant_id: int, queue: asyncio.Queue) -> None:
        if queue in self._queues[tenant_id]:
            self._queues[tenant_id].remove(queue)
        if task := self._bridge_tasks.pop(queue, None):
            task.cancel()

    async def broadcast(self, tenant_id: int, event: dict) -> None:
        if self._redis is not None:
            await self._redis.publish(f"sse:lista:{tenant_id}", json.dumps(event))
        else:
            for q in list(self._queues[tenant_id]):
                await q.put(event)

    async def _bridge(self, channel: str, queue: asyncio.Queue) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    await queue.put(json.loads(msg["data"]))
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


atendimento_sse_manager = AtendimentoSseManager()
atendimento_lista_sse_manager = AtendimentoListaSseManager()
