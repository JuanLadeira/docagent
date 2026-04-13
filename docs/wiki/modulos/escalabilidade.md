# Módulo: Escalabilidade (Redis + Celery)

> Introduzido na Fase 23.
> Arquivos: `redis_client.py`, `celery_app.py`, `tasks/`, `chat/session.py` (RedisSessionManager), `atendimento/sse.py` (bridge)

---

## Visão Geral

Três camadas de estado distribuído:

```
Redis DB0  ←  sessions (pickle, TTL 1h)
Redis DB0  ←  SSE Pub/Sub (sse:atendimento:{id}, sse:lista:{tenant_id})
Redis DB1  ←  Celery broker
Redis DB2  ←  Celery backend (resultados de tasks)
```

---

## `redis_client.py`

```python
def get_redis_client():
    if not Settings.REDIS_URL:
        return None
    return redis.asyncio.from_url(Settings.REDIS_URL, encoding="utf-8", decode_responses=False)
```

Retorna `None` se `REDIS_URL` não está configurada → todos os componentes fazem fallback para in-memory.

---

## `chat/session.py`

Três classes:

| Classe | Descrição |
|--------|-----------|
| `InMemorySessionManager` | dict local, para dev/testes |
| `RedisSessionManager` | pickle + TTL no Redis |
| `SessionManager` | alias para `InMemorySessionManager` |

Interface comum (ambas implementam):
- `async get_async(session_id) → dict`
- `async update_async(session_id, state) → None`
- `async delete_async(session_id) → bool`
- `has(session_id) → bool` (só InMemory)
- `clear() → None` (só InMemory)

Injeção via `dependencies.py`: variável de módulo `_session_manager` trocada no lifespan de `api.py` quando Redis está disponível.

---

## `atendimento/sse.py` — Bridge Pattern

Com Redis, o fluxo de eventos é:

```
broadcast(atendimento_id, event)
    └─ redis.publish("sse:atendimento:{id}", json.dumps(event))
           └─ _bridge task (por subscriber)
                  └─ queue.put(event)   ← consumido pelo SSE endpoint
```

Sem Redis (dev), `broadcast()` escreve diretamente nas queues locais.

Cada `subscribe()` cria uma `asyncio.Task` que fica em loop em `pubsub.listen()`.
`unsubscribe()` cancela a task e remove a queue.

---

## `celery_app.py`

```python
celery = Celery("docagent",
    broker=f"{redis_base}/1",
    backend=f"{redis_base}/2",
    include=["docagent.tasks.ingestao"]
)
celery.conf.update(
    task_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
```

`task_acks_late=True` garante que a task só é removida da fila após conclusão (sem perda em crash do worker).

---

## `tasks/ingestao.py`

Única task existente:

```python
@celery.task(bind=True, max_retries=3, default_retry_delay=30,
             name="docagent.tasks.ingerir_documento")
def ingerir_documento_task(self, agente_id: int, filename: str, content_b64: str) -> dict:
    content = base64.b64decode(content_b64)
    asyncio.run(_ingerir(agente_id, filename, content))
    return {"status": "ok", "agente_id": agente_id, "filename": filename}
```

`asyncio.run()` cria um novo event loop por execução (correto para workers Celery que são síncronos).

---

## TTLCache nos Routers

Em `chat/router.py`, `telegram/router.py` e `whatsapp/router.py`:

```python
_agent_cache: TTLCache = TTLCache(maxsize=100, ttl=1800)  # 30min
_cache_lock = asyncio.Lock()
```

Substitui o dict global ilimitado que crescia indefinidamente. Entradas expiram automaticamente após 30min de inatividade. `asyncio.Lock` garante que dois requests simultâneos para o mesmo agente não constroem duas instâncias.

---

## Configuração

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `REDIS_URL` | `""` | URL completa, ex: `redis://redis:6379/0`. Vazio = in-memory |
| `SKIP_MIGRATIONS` | `false` | Pula Alembic no entrypoint (usado pelos containers Celery) |
