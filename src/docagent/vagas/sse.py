import asyncio
from collections import defaultdict


class VagasPipelineSseManager:
    """SSE manager para progresso do pipeline de vagas.

    Diferente do atendimento (stream perpétuo), este stream fecha
    automaticamente ao receber CONCLUIDO ou ERRO.
    Chave: pipeline_run_id.
    """

    def __init__(self):
        self._queues: dict[int, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, pipeline_run_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[pipeline_run_id].append(q)
        return q

    def unsubscribe(self, pipeline_run_id: int, queue: asyncio.Queue) -> None:
        if queue in self._queues[pipeline_run_id]:
            self._queues[pipeline_run_id].remove(queue)

    async def broadcast(self, pipeline_run_id: int, event: dict) -> None:
        for q in list(self._queues[pipeline_run_id]):
            await q.put(event)


vagas_sse_manager = VagasPipelineSseManager()
