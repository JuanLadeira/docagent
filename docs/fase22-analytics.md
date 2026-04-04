# Fase 22 — Analytics & Observabilidade

## Objetivo

Dar visibilidade ao tenant sobre o uso da plataforma e ao time técnico sobre a saúde do sistema. Dois níveis: analytics de produto (o que o tenant quer saber sobre seus agentes e atendimentos) e observabilidade técnica (métricas, logs estruturados para o time de infra).

---

## Analytics de Produto

### Tabela: `evento_analytics`

```python
class EventoAnalytics(Base):
    __tablename__ = "evento_analytics"

    id: int (PK)
    tenant_id: int (FK → tenant)
    tipo: TipoEvento
    agente_id: int | None
    usuario_id: int | None
    canal: str | None                   # whatsapp | telegram | web
    metadados: dict (JSON)              # dados específicos por tipo
    created_at: datetime

class TipoEvento(str, Enum):
    CHAT_QUERY = "chat_query"                    # mensagem no chat web
    ATENDIMENTO_CRIADO = "atendimento_criado"
    ATENDIMENTO_ENCERRADO = "atendimento_encerrado"
    ATENDIMENTO_HUMANO = "atendimento_humano"    # operador assumiu
    RAG_HIT = "rag_hit"                          # RAG retornou resultado
    RAG_MISS = "rag_miss"                        # RAG sem resultado relevante
    DOCUMENTO_INGERIDO = "documento_ingerido"
    QUOTA_EXCEDIDA = "quota_excedida"
    AUDIO_TRANSCRITO = "audio_transcrito"
    AUDIO_SINTETIZADO = "audio_sintetizado"
    FINE_TUNE_CONCLUIDO = "fine_tune_concluido"
```

**Exemplos de metadados por tipo:**

```python
# CHAT_QUERY
{"tokens_entrada": 150, "tokens_saida": 320, "latencia_ms": 1240, "agente_id": 5}

# ATENDIMENTO_ENCERRADO
{"duracao_segundos": 480, "total_mensagens": 12, "canal": "whatsapp", "resolvido_por_agente": True}

# RAG_HIT
{"query": "prazo de rescisão", "score": 0.87, "documento_id": 3, "agente_id": 5}

# RAG_MISS
{"query": "como processar devolução", "score": 0.31}

# QUOTA_EXCEDIDA
{"recurso": "agente", "limite": 5, "tentativa": "criar_agente"}
```

### AnalyticsService

```python
class AnalyticsService:

    @staticmethod
    async def registrar(
        db: AsyncSession,
        tipo: TipoEvento,
        tenant_id: int,
        agente_id: int | None = None,
        usuario_id: int | None = None,
        canal: str | None = None,
        metadados: dict | None = None,
    ) -> None:
        evento = EventoAnalytics(tipo=tipo, tenant_id=tenant_id, ...)
        db.add(evento)
        # fire-and-forget — não bloqueia a operação principal

    @staticmethod
    async def resumo_periodo(
        tenant_id: int,
        data_inicio: date,
        data_fim: date,
        db: AsyncSession
    ) -> dict:
        # Agrega eventos por tipo e retorna contagens/médias

    @staticmethod
    async def mensagens_por_dia(
        tenant_id: int,
        agente_id: int | None,
        ultimos_dias: int,
        db: AsyncSession
    ) -> list[dict]:
        # SELECT DATE(created_at), COUNT(*) GROUP BY DATE(created_at)
        # Retorna: [{"data": "2026-04-01", "total": 42}, ...]

    @staticmethod
    async def top_agentes(
        tenant_id: int,
        ultimos_dias: int,
        db: AsyncSession
    ) -> list[dict]:
        # SELECT agente_id, COUNT(*) GROUP BY agente_id ORDER BY COUNT DESC
        # Retorna: [{"agente_id": 3, "nome": "Suporte", "total_mensagens": 280}, ...]

    @staticmethod
    async def tempo_medio_atendimento(
        tenant_id: int,
        ultimos_dias: int,
        db: AsyncSession
    ) -> float:
        # AVG(duracao_segundos) de ATENDIMENTO_ENCERRADO

    @staticmethod
    async def taxa_resolucao_agente(
        tenant_id: int,
        ultimos_dias: int,
        db: AsyncSession
    ) -> float:
        # % de atendimentos encerrados onde resolvido_por_agente=True
```

### Endpoints

```
GET /api/analytics/resumo
    → Params: data_inicio, data_fim (default: últimos 30 dias)
    → {
        total_mensagens, total_atendimentos, atendimentos_encerrados,
        taxa_resolucao_agente, tempo_medio_atendimento_segundos,
        total_documentos_ingeridos, quota_excedida_count
      }

GET /api/analytics/mensagens-por-dia
    → Params: agente_id (opcional), ultimos_dias (default: 30)
    → [{"data": "2026-04-01", "total": 42}, ...]

GET /api/analytics/top-agentes
    → Params: ultimos_dias (default: 30)
    → [{"agente_id": 1, "nome": "Bot Suporte", "total": 280, "pct": 65.2}, ...]

GET /api/analytics/atendimentos
    → Params: canal, data_inicio, data_fim
    → {
        total, por_canal: {whatsapp: X, telegram: Y},
        por_status: {encerrado: X, humano: Y, ativo: Z},
        tempo_medio_segundos
      }

GET /api/analytics/rag
    → {hits: X, misses: Y, taxa_hit_pct: 87.3, top_queries: [...]}
```

---

## Dashboard de Analytics (Frontend)

### AnalyticsView.vue

```
┌────────────────────────────────────────────────────────────┐
│ Analytics                          [Últimos 30 dias ▼]      │
│                                                            │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│ │ 1.240    │ │ 87       │ │ 94%      │ │ 4min 20s │      │
│ │ Mensagens│ │Atendiment│ │Taxa Resol│ │Tempo Med.│      │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                            │
│ Mensagens por dia ─────────────────────────────────────    │
│ [gráfico de linha — Chart.js]                              │
│                                                            │
│ Top Agentes ──────────────  Atendimentos por Canal ─────   │
│ 1. Bot Suporte   65%        [gráfico pizza]                │
│ 2. Bot Vendas    28%         WhatsApp: 72%                 │
│ 3. Bot Juridico   7%         Telegram: 28%                 │
└────────────────────────────────────────────────────────────┘
```

Usar `Chart.js` via `vue-chartjs` (já compatível com Vue 3).

---

## SLA Tracking de Atendimentos

Adicionar ao EventoAnalytics (`ATENDIMENTO_HUMANO`):

```python
metadados = {
    "tempo_ate_assumir_segundos": 180,  # quanto tempo ficou em ATIVO antes do operador assumir
    "operador_id": 7,
    "operador_username": "joao.silva"
}
```

Dashboard admin: tabela de operadores com tempo médio de resposta e volume de atendimentos.

---

## Observabilidade Técnica

### Logging Estruturado (JSON)

```python
# src/docagent/logging_config.py
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

log = structlog.get_logger()

# Uso:
log.info("chat_query", tenant_id=1, agente_id=5, latencia_ms=1240, tokens=320)
log.error("webhook_falhou", instancia="minha-instancia", erro=str(e))
```

Logs JSON são diretamente ingestáveis pelo Loki (Grafana stack) ou ELK.

### Métricas Prometheus

```python
# src/docagent/metrics.py
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app

chat_requests_total = Counter(
    "docagent_chat_requests_total",
    "Total de queries ao chat",
    ["tenant_id", "agente_id", "status"]
)
chat_latency_seconds = Histogram(
    "docagent_chat_latency_seconds",
    "Latência das queries de chat",
    ["agente_id"]
)
atendimentos_ativos = Gauge(
    "docagent_atendimentos_ativos",
    "Atendimentos ativos por canal",
    ["canal"]
)
webhook_errors_total = Counter(
    "docagent_webhook_errors_total",
    "Erros em webhooks",
    ["canal", "tipo_erro"]
)

# Montar endpoint /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**Acesso:** `/metrics` retorna formato Prometheus — scraping pelo Prometheus Server → dashboards no Grafana.

### Health Check detalhado

```python
# GET /health (expandido)
@router.get("/health")
async def health(db: AsyncSession):
    checks = {}

    # DB
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else "degraded"
    except:
        checks["ollama"] = "unreachable"

    # ChromaDB
    try:
        chroma_client.heartbeat()
        checks["chromadb"] = "ok"
    except:
        checks["chromadb"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks, "version": settings.APP_VERSION}
```

---

## Retenção de Dados

Eventos antigos aumentam o banco indefinidamente. Cron de limpeza:

```python
# Roda mensalmente
async def cron_limpar_analytics():
    # DELETE FROM evento_analytics WHERE created_at < now() - interval '6 months'
    # Manter últimos 6 meses de dados granulares
    # (agregados já estão nas queries, não precisamos dos eventos crus)
```

Configurável via `SystemConfig` (chave `analytics_retencao_meses`, default `6`).

---

## Dependências

```toml
dependencies = [
    "structlog>=24.0.0",
    "prometheus-client>=0.20.0",
]
```

**Frontend:**
```json
{
  "dependencies": {
    "vue-chartjs": "^5.0.0",
    "chart.js": "^4.0.0"
  }
}
```

---

## Testes

```
tests/test_analytics/
├── test_analytics_service.py
│   ├── test_registrar_evento
│   ├── test_resumo_periodo
│   ├── test_mensagens_por_dia_agrupado
│   ├── test_top_agentes_ordenado
│   └── test_isolamento_tenant
└── test_analytics_router.py
    ├── test_resumo_retorna_estrutura_correta
    ├── test_filtro_por_agente
    └── test_sem_dados_retorna_zeros
```

---

## Ordem de Implementação

```
1.  Branch: fase-22
2.  Alembic: tabela evento_analytics
3.  analytics/models.py + schemas.py
4.  🔴 RED: test_analytics_service.py
5.  🟢 GREEN: analytics/services.py
6.  Instrumentar pontos chave: chat/router, whatsapp/router, telegram/router, atendimento/router
7.  analytics/router.py (endpoints de query)
8.  Logging estruturado: structlog em toda a app
9.  Prometheus: metrics.py + /metrics endpoint
10. Health check detalhado em /health
11. Frontend: AnalyticsView.vue + Chart.js
12. Cron de retenção de dados
```

---

## Gotchas

- **Fire-and-forget no registrar():** envolver em `try/except` — falha no analytics não deve quebrar a feature principal
- **Índices:** `evento_analytics(tenant_id, created_at)` e `evento_analytics(tenant_id, tipo, created_at)` são obrigatórios para queries rápidas
- **Volume:** em produção com múltiplos tenants ativos, `evento_analytics` cresce rápido — implementar particionamento por mês (PostgreSQL) antes de atingir 10M+ linhas
- **/metrics não autenticado:** endpoint Prometheus tipicamente sem auth mas restrito por IP ou VPN — não expor publicamente
