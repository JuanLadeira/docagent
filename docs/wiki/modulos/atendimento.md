# Módulo: atendimento/

**Path:** `src/docagent/atendimento/`
**Fases:** 13, 14

---

## Máquina de Estados

```
ATIVO ──────────────────→ HUMANO ──→ ATIVO
  │                          │
  └──────────────────────────┴──→ ENCERRADO
```

- **ATIVO:** agente responde automaticamente
- **HUMANO:** operador assumiu, agente silenciado
- **ENCERRADO:** conversa finalizada

---

## Modelos

```python
class Atendimento(Base):
    numero: str           # phone sem @s.whatsapp.net
    nome_contato: str | None
    instancia_id: FK → whatsapp_instancia
    tenant_id: FK → tenant
    status: AtendimentoStatus   # ATIVO | HUMANO | ENCERRADO
    mensagens: → MensagemAtendimento[]

class MensagemAtendimento(Base):
    atendimento_id: FK → atendimento
    origem: MensagemOrigem   # CONTATO | AGENTE | OPERADOR
    conteudo: str
    created_at: datetime
```

---

## Endpoints REST

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/api/atendimentos` | Lista atendimentos do tenant |
| GET | `/api/atendimentos/{id}` | Detalhe com histórico |
| POST | `/api/atendimentos/{id}/assumir` | ATIVO → HUMANO |
| POST | `/api/atendimentos/{id}/devolver` | HUMANO → ATIVO |
| POST | `/api/atendimentos/{id}/encerrar` | → ENCERRADO |
| POST | `/api/atendimentos/{id}/mensagens` | Operador envia msg (só se HUMANO) |
| GET | `/api/atendimentos/{id}/eventos` | SSE stream |
| GET | `/api/atendimentos/lista/sse` | SSE lista completa (tempo real) |

---

## SSE

`AtendimentoSseManager` em `sse.py`:
- Broadcast por `atendimento_id`
- Eventos: `nova_mensagem`, `status_mudou`
- **Gotcha:** não limpa conexões mortas automaticamente. Heartbeat pendente (Fase 23).

---

## Contatos

Módulo `atendimento/contato`:
- Upsert automático ao receber mensagem (associa número a contato)
- Campos: `numero`, `nome`, `email`, `notas`, `tenant_id`
- View `ContatoView.vue` + `ContatoDetalheView.vue`

---

## Testes

25 testes TDD escritos antes da implementação (Fase 13):
- `test_sse.py` — 4 testes
- `test_services.py` — 8 testes
- `test_router.py` — 8 testes
- `test_webhook.py` — 5 testes
