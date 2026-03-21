# Fase 12 — Integração WhatsApp (Evolution API)

## Contexto

Com o DocAgent operando como plataforma multi-tenant (Fase 8) e com CRUD de agentes via interface (Fase 10), a Fase 12 adiciona um canal de atendimento via WhatsApp.

O módulo `src/docagent/whatsapp/` foi refatorado a partir de um app existente (que usava `app.*` como namespace e WebSocket para notificações). Esta fase adapta o código ao padrão DocAgent, substitui WebSocket por SSE e integra o fluxo de mensagens diretamente com o sistema de agentes — sem intermediários.

---

## Arquitetura

```
WhatsApp (usuário)
    ↕
Evolution API (self-hosted, porta 8080)
    ↕ webhook POST /api/whatsapp/webhook
DocAgent API (porta 8000)
    → busca WhatsappInstancia pelo instance_name
    → busca Agente vinculado (instancia.agente_id)
    → executa ConfigurableAgent.run(mensagem, sessao_por_numero)
    → responde via Evolution API POST /message/sendText
    ↕
WhatsApp (usuário recebe resposta)
```

Para notificações em tempo real no frontend (QR code, status de conexão):
```
Frontend Vue → GET /api/whatsapp/instancias/{id}/eventos (SSE)
Evolution API → webhook → sse_manager.broadcast() → asyncio.Queue → SSE
```

---

## Modelo de dados

### `WhatsappInstancia`

```python
class WhatsappInstancia(Base):
    __tablename__ = "whatsapp_instancia"

    instance_name: Mapped[str]          # nome único no Evolution API
    status: Mapped[ConexaoStatus]       # CRIADA | CONECTANDO | CONECTADA | DESCONECTADA
    tenant_id: Mapped[int]              # FK → Tenant (isolamento multi-tenant)
    agente_id: Mapped[int | None]       # FK → Agente (qual agente responde nesta instância)
```

`agente_id` é nullable. Instâncias sem agente vinculado ignoram mensagens recebidas.

**Session ID por contato:** `f"whatsapp:{numero}"` — garante histórico de conversa persistente por número de telefone, usando o mesmo `SessionManager` do chat web.

---

## Endpoints

### Instâncias

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/whatsapp/instancias` | User | Lista instâncias do tenant |
| POST | `/api/whatsapp/instancias` | User | Cria instância no Evolution API + banco |
| GET | `/api/whatsapp/instancias/{id}/qrcode` | User | Obtém QR code para conectar |
| GET | `/api/whatsapp/instancias/{id}/status` | User | Sincroniza status com Evolution API |
| DELETE | `/api/whatsapp/instancias/{id}` | User | Remove instância |

### Mensagens

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/api/whatsapp/instancias/{id}/mensagens/texto` | User | Envia texto via Evolution API |
| POST | `/api/whatsapp/instancias/{id}/mensagens/midia` | User | Envia mídia via Evolution API |

### Eventos SSE (substituiu WebSocket)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/whatsapp/instancias/{id}/eventos` | User | Stream SSE de eventos da instância |

Eventos emitidos:
- `{"type": "QRCODE_UPDATED", "instance_name": "...", "qr_base64": "data:image/png;base64,..."}`
- `{"type": "CONNECTION_UPDATE", "instance_name": "...", "status": "CONECTADA"}`
- `{"type": "ping"}` — keepalive a cada 30s

### Webhook (recebe da Evolution API)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/api/whatsapp/webhook` | Nenhuma | Recebe eventos da Evolution API |

Eventos processados: `QRCODE_UPDATED`, `CONNECTION_UPDATE`, `MESSAGES_UPSERT`.

---

## Fluxo de mensagem recebida

```
POST /api/whatsapp/webhook
  evento.event == "MESSAGES_UPSERT"
    → ignorar mensagens fromMe
    → extrair conteudo (conversation ou extendedTextMessage.text)
    → extrair numero = remoteJid.replace("@s.whatsapp.net", "")
    → session_id = f"whatsapp:{numero}"
    → buscar WhatsappInstancia por instance_name
    → buscar Agente por instancia.agente_id (deve estar ativo)
    → ConfigurableAgent(config, system_prompt_override=agente.system_prompt).build()
    → state = SessionManager.get(session_id)
    → final_state = agent.run(conteudo, state)
    → SessionManager.update(session_id, agent.last_state)
    → extrair AIMessage final → answer
    → POST Evolution API /message/sendText/{instance_name}
         {"number": numero, "text": answer}
```

---

## SSE Manager

`src/docagent/whatsapp/ws_manager.py` (reescrito — era WebSocket manager):

```python
class SseManager:
    _queues: dict[int, list[asyncio.Queue]]  # por tenant_id

    async def subscribe(tenant_id) → asyncio.Queue
    def unsubscribe(tenant_id, queue)
    async def broadcast(tenant_id, event: dict)

sse_manager = SseManager()  # singleton global
```

---

## Variáveis de ambiente

```env
EVOLUTION_API_URL=http://evolution-api:8080   # URL interna da Evolution API
EVOLUTION_API_KEY=changeme                     # API key configurada na Evolution API
WEBHOOK_BASE_URL=http://api:8000               # URL base do DocAgent (para a Evolution saber onde mandar webhooks)
```

---

## Docker Compose

```yaml
services:
  evolution-api:
    image: atendai/evolution-api:v2.2.3
    ports: ["8080:8080"]
    environment:
      SERVER_URL: http://localhost:8080
      AUTHENTICATION_API_KEY: ${EVOLUTION_API_KEY:-changeme}
      DATABASE_ENABLED: "false"
      CACHE_REDIS_ENABLED: "false"
    volumes:
      - evolution_data:/evolution/instances

volumes:
  evolution_data:
```

---

## Verificação end-to-end

```bash
# 1. Subir todos os serviços
docker compose up -d

# 2. Verificar Evolution API
curl http://localhost:8080/instance/fetchInstances \
  -H "apikey: changeme"

# 3. Obter token DocAgent
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin" | jq -r .access_token)

# 4. Criar instância vinculada ao agente 1
curl -X POST http://localhost:8000/api/whatsapp/instancias \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"instance_name": "docagent-bot", "agente_id": 1}'

# 5. Obter QR code para conectar
curl "http://localhost:8000/api/whatsapp/instancias/1/qrcode" \
  -H "Authorization: Bearer $TOKEN"
# Abrir o qr_base64 num <img> HTML para escanear

# 6. Escutar eventos SSE (QR code e status chegam aqui em tempo real)
curl -N "http://localhost:8000/api/whatsapp/instancias/1/eventos" \
  -H "Authorization: Bearer $TOKEN"

# 7. Enviar mensagem no WhatsApp e verificar resposta nos logs
docker compose logs api -f
```

---

## Notas de implementação

- **WebSocket → SSE**: O `ws_manager.py` foi reescrito mantendo o mesmo filename, agora expõe `sse_manager` (`SseManager`) em vez de `ws_manager` (`ConnectionManager`).
- **Session per contact**: `session_id = f"whatsapp:{numero}"` — o agente lembra do histórico de cada número usando o mesmo `SessionManager` singleton do chat web.
- **Webhook sem DI**: O handler do webhook usa `AsyncSessionLocal()` diretamente (sem `Depends()`, que não funciona fora do ciclo de request normal do FastAPI).
- **Multi-tenant**: `instancia.tenant_id` isola os dados; o `sse_manager` faz broadcast apenas para as conexões SSE do mesmo tenant.
- **Sem n8n**: A integração é direta — Evolution API → DocAgent webhook → agente → Evolution API. N8n não é necessário para o fluxo principal.
