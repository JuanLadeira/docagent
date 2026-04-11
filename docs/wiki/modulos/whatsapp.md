# Módulo: whatsapp/

**Path:** `src/docagent/whatsapp/`
**Fases:** 12, 13, 18
**Gateway:** Evolution API v2.3.7 (self-hosted, PostgreSQL próprio)

---

## Fluxo Principal

```
Usuário → WhatsApp → Evolution API → POST /api/whatsapp/webhook
  ├─ Ignora grupos (@g.us)
  ├─ Ignora mensagens próprias (fromMe=true)
  ├─ Upsert Atendimento (ATIVO | HUMANO | ENCERRADO)
  ├─ Salva MensagemAtendimento(CONTATO)
  ├─ Broadcast SSE
  ├─ Se HUMANO → para aqui
  ├─ Se audioMessage + STT habilitado → transcreve → agente → responde áudio/texto
  └─ Se texto → agente → responde texto
```

---

## Endpoints REST

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/api/whatsapp/instancias` | Lista instâncias do tenant |
| POST | `/api/whatsapp/instancias` | Cria instância |
| DELETE | `/api/whatsapp/instancias/{id}` | Remove instância |
| GET | `/api/whatsapp/instancias/{id}/qr` | QR code WebSocket |
| POST | `/api/whatsapp/webhook` | Recebe eventos da Evolution API |

---

## Detecção de Áudio no Webhook

```python
message_content = msg.get("message", {})
if "audioMessage" in message_content:
    # baixar via /chat/getBase64FromMediaMessage/{instance}
    # resolver AudioConfig → transcrever → agente → enviar resposta
```

**Gotcha:** A Evolution API pode retornar a mídia como base64 no payload ou como URL temporária.
Usar explicitamente `/chat/getBase64FromMediaMessage` para forçar base64.

---

## Helpers no Router

- `_baixar_midia_evolution(instance_name, message_id)` → `bytes`
- `_executar_agente_whatsapp(instancia, texto, numero, db)` → `str`
- `_enviar_resposta_whatsapp(instancia, numero, texto, config, db)` → envia áudio ou texto
- `_enviar_texto_evolution(instance_name, numero, texto)` → texto puro

---

## Instância WhatsApp

```python
class WhatsappInstancia(Base):
    instance_name: str        # identificador na Evolution API
    tenant_id: FK → tenant
    agente_id: FK → agente (nullable)
    cria_atendimentos: bool   # True = modo atendimento, False = modo direto
    status: WhatsappStatus
```

---

## Variáveis de Ambiente

```env
EVOLUTION_API_URL=http://evolution-api:8080
EVOLUTION_API_KEY=changeme
WEBHOOK_BASE_URL=http://api:8000
```
