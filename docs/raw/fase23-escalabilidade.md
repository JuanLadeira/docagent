# Fase 23 — Escalabilidade

## Objetivo

Preparar a plataforma para múltiplos workers e alta carga. Hoje vários componentes usam estado em memória (SessionManager, SSE managers, agent cache) — o que quebra silenciosamente com mais de uma réplica. Esta fase substitui esses componentes por soluções distribuídas.

---

## Problemas atuais com múltiplos workers

| Componente | Problema hoje | Solução |
|------------|---------------|---------|
| `SessionManager` | dict em memória por worker | Redis |
| `AtendimentoSseManager` | lista de subscritores local | Redis Pub/Sub |
| `_agent_cache` (chat router) | cresce indefinidamente, local | LRU + TTL via cachetools ou Redis |
| Fine-tuning jobs | processo filho por worker | Celery worker dedicado |
| PDF ingestão (grandes) | bloqueia worker durante chunks | Celery task assíncrona |
| Email transacional | chamada síncrona em endpoint | Celery task |

---

## 1. Redis como SessionManager

### Hoje

```python
class SessionManager:
    _sessions: dict[str, list[BaseMessage]] = {}  # local
```

### Novo

```python
import redis.asyncio as redis
import pickle

class SessionManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.ttl = 3600  # 1 hora de inatividade → sessão expira

    async def get_history(self, session_id: str) -> list[BaseMessage]:
        data = await self.redis.get(f"session:{session_id}")
        if data is None:
            return []
        return pickle.loads(data)

    async def save_history(self, session_id: str, messages: list[BaseMessage]) -> None:
        await self.redis.setex(
            f"session:{session_id}",
            self.ttl,
            pickle.dumps(messages)
        )

    async def delete(self, session_id: str) -> None:
        await self.redis.delete(f"session:{session_id}")
```

TTL automático do Redis garante cleanup de sessões antigas sem cron.

---

## 2. SSE via Redis Pub/Sub

### Problema atual

```python
# sse.py — hoje
class AtendimentoSseManager:
    _subscriptions: dict[int, list[asyncio.Queue]] = {}
    # Worker A tem as filas do atendimento X
    # Worker B não tem → cliente conectado no B não recebe eventos do A
```

### Novo: Redis Pub/Sub

```python
class AtendimentoSseManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def publicar(self, tenant_id: int, evento: dict) -> None:
        channel = f"sse:tenant:{tenant_id}"
        await self.redis.publish(channel, json.dumps(evento))

    async def publicar_atendimento(self, atendimento_id: int, evento: dict) -> None:
        channel = f"sse:atendimento:{atendimento_id}"
        await self.redis.publish(channel, json.dumps(evento))

    async def subscribe_tenant(self, tenant_id: int) -> AsyncGenerator[str, None]:
        """Gerador SSE: escuta eventos do tenant inteiro (lista de atendimentos)"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"sse:tenant:{tenant_id}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data'].decode()}\n\n"
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()

    async def subscribe_atendimento(self, atendimento_id: int) -> AsyncGenerator[str, None]:
        """Gerador SSE: escuta mensagens de um atendimento específico"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"sse:atendimento:{atendimento_id}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data'].decode()}\n\n"
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()
```

Os routers de atendimento e whatsapp continuam chamando `publicar()` — só a implementação interna muda.

---

## 3. Agent Cache com LRU + TTL

### Hoje

```python
# chat/router.py
_agent_cache: dict[str, tuple] = {}  # cresce para sempre
```

### Novo

```python
from cachetools import TTLCache
import asyncio

# Cache com máx 100 agentes, TTL de 30 minutos
_agent_cache: TTLCache = TTLCache(maxsize=100, ttl=1800)
_cache_lock = asyncio.Lock()

async def get_or_build_agent(cache_key: str, builder_fn) -> CompiledGraph:
    async with _cache_lock:
        if cache_key in _agent_cache:
            return _agent_cache[cache_key]
        agent = await builder_fn()
        _agent_cache[cache_key] = agent
        return agent
```

Com múltiplos workers: cache local por worker é aceitável aqui — o pior caso é reconstruir o agente uma vez por worker. Diferente do SSE e sessão onde o estado precisa ser compartilhado.

---

## 4. Celery para Tarefas Longas

### Por que Celery

Tarefas que hoje bloqueiam o worker ou são síncronas em endpoints:

| Tarefa | Tempo | Problema atual |
|--------|-------|----------------|
| Fine-tuning (Unsloth) | horas | `ThreadPoolExecutor` no processo principal |
| Ingestão de PDF grande | segundos/minutos | bloqueia worker durante chunks |
| Envio de email | ~500ms | síncrono no endpoint |
| Cron de grace period | periódico | APScheduler no processo principal |
| Coleta de dataset de atendimentos | segundos | chamada síncrona |

### Setup

```python
# celery_app.py
from celery import Celery

celery = Celery(
    "docagent",
    broker="redis://redis:6379/1",
    backend="redis://redis:6379/2",
)

celery.conf.update(
    task_serializer="json",
    result_expires=86400,  # 24h
    timezone="America/Sao_Paulo",
    beat_schedule={
        "reconciliar-assinaturas": {
            "task": "docagent.tasks.cron_reconciliar_assinaturas",
            "schedule": crontab(hour=3, minute=0),  # 3h da manhã todo dia
        },
        "limpar-analytics": {
            "task": "docagent.tasks.cron_limpar_analytics",
            "schedule": crontab(day_of_month=1, hour=2),  # 1º de cada mês
        },
    },
)
```

### Tasks

```python
# tasks/fine_tuning.py
@celery.task(bind=True, max_retries=0)
def executar_fine_tune(self, job_id: int):
    # Idêntico ao _executar_treino atual
    # Atualiza fine_tune_job.status e log_saida periodicamente

# tasks/ingestao.py
@celery.task
def ingerir_documento(documento_id: int, pdf_path: str, tenant_id: int):
    # Pipeline de ingestão PDF → ChromaDB

# tasks/email.py
@celery.task
def enviar_email(tipo: str, destinatario: str, dados: dict):
    # EmailService.enviar_*

# tasks/crons.py
@celery.task
def cron_reconciliar_assinaturas():
    # AssinaturaService: GRACE vencidos → VENCIDA, etc.

@celery.task
def cron_limpar_analytics():
    # DELETE evento_analytics WHERE created_at < 6 meses
```

### Docker Compose — novo serviço

```yaml
celery-worker:
  build:
    context: .
    dockerfile: compose/prod/api/Dockerfile
  command: uv run celery -A docagent.celery_app worker --loglevel=info --concurrency=2
  environment:
    # mesmas envs que api
    REDIS_URL: redis://redis:6379
    DOCAGENT_DB_URL: ...
  depends_on:
    - redis
    - postgres
  volumes:
    - ./data:/app/data

celery-beat:
  build:
    context: .
    dockerfile: compose/prod/api/Dockerfile
  command: uv run celery -A docagent.celery_app beat --loglevel=info
  depends_on:
    - redis

redis:
  image: redis:7-alpine
  volumes:
    - redis_data:/data
  restart: unless-stopped
```

---

## 5. Redis no docker-compose.cloudflare.yml

```yaml
redis:
  image: redis:7-alpine
  volumes:
    - redis_data:/var/lib/redis/data
  networks:
    - internal
  restart: unless-stopped

volumes:
  redis_data:
```

---

## Dependências

```toml
dependencies = [
    "redis[asyncio]>=5.0.0",
    "celery[redis]>=5.3.0",
    "cachetools>=5.3.0",
    "flower>=2.0.0",        # UI de monitoramento do Celery (opcional)
]
```

---

## Ordem de Implementação

```
1.  Branch: fase-23
2.  Adicionar Redis ao docker-compose (dev + prod)
3.  SessionManager → Redis (com fallback em memória para testes)
4.  AtendimentoSseManager → Redis Pub/Sub
5.  _agent_cache → TTLCache (cachetools)
6.  celery_app.py + tasks básicas (email)
7.  Fine-tuning job → Celery task
8.  Ingestão PDF → Celery task
9.  Crons: reconciliar_assinaturas, limpar_analytics → Celery beat
10. Docker Compose: adicionar celery-worker, celery-beat, redis
11. Testes: mockar Redis com fakeredis
```

---

## Testes

```
tests/test_escalabilidade/
├── test_session_manager_redis.py
│   ├── test_salvar_e_recuperar_historico      — fakeredis
│   ├── test_expiracao_ttl
│   └── test_worker_diferente_ve_mesma_sessao  — simula 2 workers
├── test_sse_redis.py
│   ├── test_publicar_e_receber_evento
│   └── test_dois_workers_recebem_mesmo_evento
└── test_celery_tasks.py
    ├── test_fine_tune_task_muda_status
    ├── test_ingestao_task_processa_pdf
    └── test_email_task_chama_email_service
```

**fakeredis** — Redis em memória para testes, sem precisar de container:
```toml
dev-dependencies = ["fakeredis>=2.20.0"]
```

---

## Gotchas

- **Serialização de BaseMessage:** `pickle` funciona mas é frágil a mudanças de schema. Alternativa: serializar via `.dict()` do LangChain e reidratar com `messages_from_dict()`.
- **Celery + async:** Celery é síncrono por padrão. Para chamar código async dentro de tasks: `asyncio.run(minha_coroutine())` ou usar `celery[eventlet]`.
- **SSE heartbeat:** conexões SSE abertas sem mensagem fecham após timeout do nginx/proxy. Adicionar heartbeat a cada 30s: `yield ": keep-alive\n\n"`.
- **Flower em produção:** expor o Flower (`:5555`) apenas na rede interna, nunca publicamente.
- **Redis persistence:** configurar `appendonly yes` no Redis para não perder sessões em restart.
