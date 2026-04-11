# Gotchas — DocAgent

Armadilhas reais encontradas durante o desenvolvimento. Cada entrada tem causa, sintoma e solução.

---

## Banco de Dados / ORM

### FK aponta para tablename errado
**Sintoma:** `sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'audio_config.agente_id' could not find table 'agentes'`
**Causa:** O modelo `Agente` tem `__tablename__ = "agente"` (singular), mas a FK foi escrita como `ForeignKey("agentes.id")`.
**Solução:** Sempre usar `ForeignKey("agente.id")`. Checar o `__tablename__` do modelo alvo antes de escrever FKs.
**Onde aconteceu:** AudioConfig (Fase 18), migração Alembic correspondente.

### `AudioConfig.__new__()` quebra o ORM
**Sintoma:** `TypeError: AudioConfig.__new__() takes 1 positional argument but 2 were given` ao tentar instanciar `AudioConfig.__new__(AudioConfig)` como fallback de system defaults.
**Causa:** SQLAlchemy injeta `_sa_instance_state` via `__init__`. Usar `__new__` bypassa isso.
**Solução:** Usar `types.SimpleNamespace(id=None, stt_habilitado=False, ...)` para system defaults. Não é um objeto ORM, mas tem os mesmos atributos.
**Onde aconteceu:** `AudioService._system_defaults()` (Fase 18).

### Tenant sem campo `slug`
**Sintoma:** `TypeError: Tenant.__init__() got an unexpected keyword argument 'slug'`
**Causa:** O modelo `Tenant` não tem campo `slug` — só `nome`.
**Solução:** Fixtures de teste só passam `nome=...`.

### `batch_alter_table` é obrigatório no SQLite
**Causa:** SQLite não suporta `ALTER COLUMN` nativo.
**Solução:** Sempre usar `with op.batch_alter_table("tabela") as batch_op:` nas migrations Alembic quando há mudança em colunas existentes (não só adição de novas colunas).

---

## Enums e Constantes

### `TelegramBotStatus.ATIVO` não existe
**Sintoma:** `AttributeError: ATIVO is not a valid TelegramBotStatus`
**Causa:** O enum correto é `TelegramBotStatus.ATIVA` (feminino, pois "instância" é feminina).
**Solução:** Sempre checar o valor exato do enum no modelo antes de usar em testes.

---

## Testes (pytest-asyncio strict)

### Patch no caminho errado
**Sintoma:** mock não tem efeito, função original é chamada.
**Causa:** `patch("asyncio.get_event_loop")` não funciona para mockar `run_in_executor` no contexto do router.
**Solução:** Mockar diretamente a função helper do router: `patch("docagent.telegram.router._executar_agente_telegram", new_callable=AsyncMock, return_value="")`.

### Conftest com typo
**Arquivo:** `tests/confttest.py` (typo — dois `t`) — esse arquivo existe mas pytest não o descobre automaticamente.
**Solução:** Renomear para `tests/conftest.py`. Até ser corrigido, fixtures globais definidas lá não são carregadas.

### `asyncio_mode = "strict"` exige `@pytest.mark.asyncio` em todo teste async
Configurado em `pyproject.toml`. Não usar `asyncio_mode = "auto"`. Todo teste async precisa do decorator explícito.

---

## MCP / LangGraph

### Subprocessos MCP órfãos
**Sintoma:** processos `npx` sobrevivem após o chat terminar.
**Causa:** `AsyncExitStack` precisa envolver **todo** o generator do stream, não só a inicialização.
**Solução:** O `async with stack:` fica dentro do `managed_stream()` generator, que só fecha quando o último chunk SSE é entregue.

### `_agent_cache` cresce sem limite
**Localização:** `routers/chat.py` e `telegram/router.py`.
**Risco:** memory leak em produção com muitos agentes/tenants distintos.
**Solução pendente:** Substituir por `TTLCache` com LRU (planejado para Fase 23).

---

## WhatsApp / Evolution API

### Evolution API retorna base64 ou URL dependendo da config
**Contexto:** Ao baixar mídia (audioMessage), a API pode retornar base64 diretamente no payload ou uma URL temporária — depende da configuração `STORE_MESSAGES` na Evolution API.
**Solução:** Usar o endpoint `/chat/getBase64FromMediaMessage/{instance}` explicitamente para forçar base64.

### SSE managers não limpam conexões mortas
**Sintoma:** Após desconexão de cliente SSE, o slot fica na lista de subscribers.
**Solução pendente:** Adicionar heartbeat periódico + cleanup de generators mortos (Fase 23).

---

## Frontend / TypeScript

### Import não utilizado quebra `vue-tsc`
**Sintoma:** `error TS6133: 'baseApi' is declared but its value is never read` → build falha.
**Onde aconteceu:** `audioClient.ts` importava `api as baseApi` de `@/api/client` sem usar.
**Solução:** Remover o import. O `vue-tsc` (TypeScript strict) roda no build de produção — sempre checar antes do `prod-build`.

---

## Segurança (pendente Fase 21)

### Secrets em plaintext no banco
- `llm_api_key` (system_config) — plaintext
- `elevenlabs_api_key` (audio_config) — plaintext
- `bot_token` (telegram_instancia, whatsapp_instancia) — plaintext

**Solução planejada:** Fernet encryption via `AUDIO_FERNET_KEY` / `SECRET_FERNET_KEY` env vars (Fase 21).
A infra Fernet já está na `settings.py` para `AUDIO_FERNET_KEY` — só falta aplicar nos outros campos.
