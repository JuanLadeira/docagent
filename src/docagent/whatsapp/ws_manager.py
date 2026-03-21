"""
SSE Manager para notificações em tempo real de eventos WhatsApp.

Substitui o WebSocket manager anterior — usa asyncio.Queue por tenant
para fazer broadcast de eventos (QR code, status de conexão) via SSE.
"""
import asyncio
from collections import defaultdict


class SseManager:
    def __init__(self):
        self._queues: dict[int, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, tenant_id: int) -> asyncio.Queue:
        """Registra uma nova fila SSE para o tenant. Retorna a fila."""
        q: asyncio.Queue = asyncio.Queue()
        self._queues[tenant_id].append(q)
        return q

    def unsubscribe(self, tenant_id: int, queue: asyncio.Queue) -> None:
        """Remove a fila SSE quando o cliente desconecta."""
        if queue in self._queues[tenant_id]:
            self._queues[tenant_id].remove(queue)

    async def broadcast(self, tenant_id: int, event: dict) -> None:
        """Envia um evento para todas as conexões SSE ativas do tenant."""
        for q in list(self._queues[tenant_id]):
            await q.put(event)


sse_manager = SseManager()
