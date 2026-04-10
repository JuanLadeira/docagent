# Fase 18 — Mensagens de Áudio (STT + TTS)

## Objetivo

Permitir que agentes recebam mensagens de áudio (WhatsApp e Telegram), transcrevam para texto, processem normalmente e respondam com áudio sintetizado — tudo configurável por agente, com fallback para uma config padrão do tenant.

---

## Comportamento esperado

```
Usuário envia áudio no WhatsApp/Telegram
  → Backend baixa o arquivo de áudio
  → STT: transcreve para texto (faster-whisper local ou OpenAI Whisper)
  → Agente processa o texto normalmente (LangGraph)
  → Se TTS habilitado:
      → TTS: sintetiza resposta em áudio (Piper local, OpenAI TTS ou ElevenLabs)
      → Envia áudio como mensagem de voz
      → Se modo = audio_e_texto: envia também a transcrição da resposta em texto
      → Se modo = audio_apenas: só o áudio
  → Se TTS desabilitado:
      → Envia resposta só em texto (comportamento atual)
```

---

## Resolução de configuração (cascata)

```
1. Agente tem AudioConfig própria?  → usa ela
2. Tenant tem AudioConfig padrão?   → usa ela  (agente_id IS NULL)
3. Nenhuma configurada              → system defaults (ver abaixo)
```

**System defaults (hardcoded em settings.py):**
- `stt_habilitado = False`
- `stt_provider = faster_whisper`
- `stt_modelo = base`
- `tts_habilitado = False`
- `tts_provider = piper`
- `modo_resposta = audio_e_texto`

---

## Schema — Banco de Dados

### Nova tabela: `audio_config`

```python
class AudioConfig(Base):
    __tablename__ = "audio_config"

    id: int (PK)
    tenant_id: int (FK → tenant, NOT NULL)
    agente_id: int | None (FK → agente, nullable)
    # agente_id IS NULL → config padrão do tenant
    # agente_id preenchido → config específica do agente

    # STT — Speech-to-Text
    stt_habilitado: bool = False
    stt_provider: SttProvider = "faster_whisper"  # faster_whisper | openai
    stt_modelo: str = "base"  # tiny | base | small | medium | large-v3

    # TTS — Text-to-Speech
    tts_habilitado: bool = False
    tts_provider: TtsProvider = "piper"  # piper | openai | elevenlabs
    piper_voz: str = "pt_BR-faber-medium"  # modelo de voz Piper
    openai_tts_voz: str = "nova"  # alloy | echo | fable | onyx | nova | shimmer
    elevenlabs_voice_id: str | None = None
    elevenlabs_api_key: str | None = None  # criptografado (Fernet)

    # Modo de resposta
    modo_resposta: ModoResposta = "audio_e_texto"
    # audio_apenas | texto_apenas | audio_e_texto

    created_at: datetime
    updated_at: datetime

    __table_args__ = (
        UniqueConstraint("tenant_id", "agente_id"),
        # garante: 1 config padrão por tenant + 1 config por agente
    )
```

**Enums:**
```python
class SttProvider(str, Enum):
    FASTER_WHISPER = "faster_whisper"
    OPENAI = "openai"

class TtsProvider(str, Enum):
    PIPER = "piper"
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"

class ModoResposta(str, Enum):
    AUDIO_APENAS = "audio_apenas"
    TEXTO_APENAS = "texto_apenas"
    AUDIO_E_TEXTO = "audio_e_texto"
```

---

## Estrutura de Arquivos

```
src/docagent/audio/
├── __init__.py
├── models.py          — AudioConfig, SttProvider, TtsProvider, ModoResposta
├── schemas.py         — AudioConfigCreate, AudioConfigUpdate, AudioConfigPublic
├── services.py        — AudioService (transcrever + sintetizar + resolver_config)
├── stt/
│   ├── __init__.py
│   ├── faster_whisper.py   — FasterWhisperSTT
│   └── openai_whisper.py   — OpenAIWhisperSTT
└── tts/
    ├── __init__.py
    ├── piper.py             — PiperTTS
    ├── openai_tts.py        — OpenAITTS
    └── elevenlabs.py        — ElevenLabsTTS

src/docagent/audio/router.py
    — GET  /api/audio-config/default          → config padrão do tenant
    — PUT  /api/audio-config/default          → salvar/atualizar config padrão
    — GET  /api/agentes/{id}/audio-config     → config do agente (ou padrão se não tiver)
    — PUT  /api/agentes/{id}/audio-config     → salvar/atualizar config do agente
    — DELETE /api/agentes/{id}/audio-config   → remove config específica (volta ao padrão)
```

---

## AudioService

```python
class AudioService:

    async def resolver_config(
        agente_id: int,
        tenant_id: int,
        db: AsyncSession
    ) -> AudioConfig:
        # 1. Tenta config específica do agente
        # 2. Tenta config padrão do tenant (agente_id IS NULL)
        # 3. Retorna system defaults

    async def transcrever(
        audio_bytes: bytes,
        config: AudioConfig,
        openai_api_key: str | None = None
    ) -> str:
        # Delega para FasterWhisperSTT ou OpenAIWhisperSTT
        # Retorna texto transcrito

    async def sintetizar(
        texto: str,
        config: AudioConfig,
        openai_api_key: str | None = None
    ) -> bytes:
        # Delega para PiperTTS, OpenAITTS ou ElevenLabsTTS
        # Retorna bytes do áudio em formato OGG/OPUS
```

### STT — FasterWhisperSTT

```python
class FasterWhisperSTT:
    # Singleton: carrega modelo uma vez, reutiliza
    _model: WhisperModel | None = None

    @classmethod
    def get_model(cls, modelo: str) -> WhisperModel:
        if cls._model is None:
            cls._model = WhisperModel(modelo, device="cpu", compute_type="int8")
        return cls._model

    async def transcrever(self, audio_bytes: bytes, modelo: str) -> str:
        # Salva bytes em arquivo temporário
        # Roda model.transcribe() em thread pool (run_in_executor)
        # Retorna texto concatenado dos segmentos
```

### TTS — PiperTTS

```python
class PiperTTS:
    async def sintetizar(self, texto: str, voz: str) -> bytes:
        # Roda piper via subprocess (piper --model {voz} --output_file -)
        # Piper gera WAV → converter para OGG/OPUS via ffmpeg
        # Retorna bytes OGG/OPUS
        # Roda em thread pool para não bloquear o event loop
```

**Vozes Piper disponíveis para pt-BR:**
- `pt_BR-faber-medium` — voz masculina, qualidade média (recomendado)
- `pt_BR-edresson-low` — voz masculina, qualidade baixa (mais rápido)

---

## Integração com WhatsApp

**Arquivo:** `src/docagent/whatsapp/router.py` — handler do webhook

### Detectar áudio no payload Evolution API

```python
# Evento MESSAGES_UPSERT com audioMessage
{
  "event": "MESSAGES_UPSERT",
  "data": {
    "messages": [{
      "key": {"remoteJid": "5511999999999@s.whatsapp.net"},
      "message": {
        "audioMessage": {
          "url": "https://...",
          "mimetype": "audio/ogg; codecs=opus",
          "seconds": 12,
          "ptt": true  # push-to-talk = mensagem de voz
        }
      }
    }]
  }
}
```

**Fluxo no webhook:**
```python
async def _processar_mensagem_whatsapp(evento, instancia, db):
    msg = evento["data"]["messages"][0]
    message_content = msg.get("message", {})

    if "audioMessage" in message_content:
        # 1. Baixar áudio via Evolution API
        audio_bytes = await evolution_client.download_media(
            instancia.instance_name,
            msg["key"]["id"]
        )
        # 2. Resolver config de áudio do agente
        audio_config = await AudioService.resolver_config(
            agente_id=instancia.agente_id,
            tenant_id=instancia.tenant_id,
            db=db
        )
        if not audio_config.stt_habilitado:
            return  # ignora áudio se STT desabilitado

        # 3. Transcrever
        texto = await AudioService.transcrever(audio_bytes, audio_config)

        # 4. Processar pelo agente (igual texto normal)
        resposta_texto = await _executar_agente(instancia, texto, db)

        # 5. Responder
        await _enviar_resposta_whatsapp(
            instancia, numero, resposta_texto, audio_config, db
        )

    elif "conversation" in message_content or "extendedTextMessage" in message_content:
        # fluxo atual de texto — sem mudanças
        ...

async def _enviar_resposta_whatsapp(instancia, numero, texto, config, db):
    if config.tts_habilitado:
        audio_bytes = await AudioService.sintetizar(texto, config)
        await evolution_client.enviar_audio(
            instancia.instance_name, numero, audio_bytes
        )
        if config.modo_resposta == ModoResposta.AUDIO_E_TEXTO:
            await evolution_client.enviar_texto(instancia.instance_name, numero, texto)
    else:
        await evolution_client.enviar_texto(instancia.instance_name, numero, texto)
```

### Novo método no Evolution client

```python
async def enviar_audio(
    self,
    instance_name: str,
    numero: str,
    audio_bytes: bytes
) -> dict:
    # POST /message/sendWhatsAppAudio/{instance_name}
    # Body: { "number": numero, "audio": base64(audio_bytes), "encoding": true }
```

---

## Integração com Telegram

**Arquivo:** `src/docagent/telegram/router.py` — handler do webhook

### Detectar áudio no payload Telegram

```python
# Update com voice (mensagem de voz gravada)
{
  "update_id": 123,
  "message": {
    "chat": {"id": 987654321},
    "voice": {
      "file_id": "AwACAgIA...",
      "duration": 8,
      "mime_type": "audio/ogg",
      "file_size": 12345
    }
  }
}

# Update com audio (arquivo de áudio enviado)
{
  "message": {
    "audio": {
      "file_id": "...",
      "duration": 30,
      "mime_type": "audio/mpeg"
    }
  }
}
```

**Fluxo no webhook:**
```python
async def _processar_update_telegram(update, instancia, db):
    message = update.get("message", {})
    voice = message.get("voice") or message.get("audio")

    if voice:
        # 1. Obter file_path via getFile
        file_info = await telegram_client.get_file(
            instancia.bot_token, voice["file_id"]
        )
        # 2. Baixar arquivo
        audio_bytes = await telegram_client.download_file(
            instancia.bot_token, file_info["file_path"]
        )
        # 3. Resolver config + transcrever + processar + responder
        # (mesmo fluxo do WhatsApp)
        ...
```

### Novo método no Telegram client

```python
async def enviar_audio(
    self,
    bot_token: str,
    chat_id: int,
    audio_bytes: bytes
) -> dict:
    # POST /sendVoice
    # multipart/form-data: chat_id + voice (arquivo OGG/OPUS)
```

---

## Dependências a adicionar

```toml
# pyproject.toml
dependencies = [
    # STT
    "faster-whisper>=1.0.0",

    # TTS
    "piper-tts>=1.2.0",

    # Conversão de áudio (WAV → OGG/OPUS)
    # ffmpeg precisa estar instalado no sistema (já está no Dockerfile base geralmente)
    # Wrapper Python:
    "ffmpeg-python>=0.2.0",

    # Criptografia para elevenlabs_api_key
    "cryptography>=42.0.0",  # já pode estar no projeto
]
```

**Dockerfile (compose/prod/api/Dockerfile):** adicionar `ffmpeg` e baixar modelos Piper/Whisper no build:
```dockerfile
RUN apt-get install -y ffmpeg

# Pré-baixar modelo Piper (evita download em runtime)
RUN python -c "from piper import PiperVoice; PiperVoice.load('pt_BR-faber-medium')"

# Pré-baixar modelo Whisper base
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu')"
```

---

## Frontend — Configuração de Áudio

### Onde fica na UI

- **Configuração padrão do tenant:** `SettingsView.vue` → nova aba "Áudio"
- **Configuração por agente:** `AgenteFormView.vue` → nova seção "Configurações de Áudio"

### Componente `AudioConfigForm.vue`

```
┌─────────────────────────────────────────────┐
│ Configurações de Áudio                       │
│                                              │
│ [x] Transcrição de áudio (STT)               │
│     Provider: [faster-whisper ▼]             │
│     Modelo:   [base          ▼]              │
│               tiny/base/small/medium/large   │
│                                              │
│ [x] Resposta em áudio (TTS)                  │
│     Provider: [Piper         ▼]              │
│     Voz:      [pt_BR-faber-medium ▼]         │
│                                              │
│     Modo de resposta:                        │
│     (●) Áudio + texto                        │
│     ( ) Somente áudio                        │
│     ( ) Somente texto                        │
│                                              │
│ ℹ️ Agentes sem config própria usam esta       │
│    configuração como padrão.                 │
└─────────────────────────────────────────────┘
```

Quando provider = OpenAI: mostra campo de API key (usa a do tenant se já configurada).
Quando provider = ElevenLabs: mostra campos Voice ID + API key.

---

## Testes (TDD)

```
tests/test_audio/
├── __init__.py
├── conftest.py                   — fixtures: db, client, instancia_wpp, instancia_tg
├── test_audio_service.py
│   ├── test_resolver_config_agente_proprio    — agente com config → usa ela
│   ├── test_resolver_config_fallback_tenant   — sem config no agente → usa do tenant
│   ├── test_resolver_config_system_default    — sem config em nenhum → system defaults
│   ├── test_transcrever_faster_whisper        — mock WhisperModel.transcribe
│   └── test_sintetizar_piper                  — mock subprocess Piper
├── test_stt_providers.py
│   ├── test_faster_whisper_singleton          — modelo carregado só uma vez
│   └── test_openai_whisper                    — mock httpx, retorna texto
├── test_tts_providers.py
│   ├── test_piper_gera_ogg                    — mock subprocess, retorna bytes OGG
│   ├── test_openai_tts                        — mock httpx, retorna bytes MP3
│   └── test_elevenlabs_tts                    — mock httpx, retorna bytes MP3
├── test_webhook_whatsapp_audio.py
│   ├── test_audio_message_transcrito_e_processado
│   ├── test_audio_ignorado_se_stt_desabilitado
│   ├── test_resposta_audio_apenas
│   ├── test_resposta_audio_e_texto
│   ├── test_resposta_texto_apenas_mesmo_com_audio_recebido
│   └── test_texto_normal_nao_afetado          — regressão
└── test_webhook_telegram_audio.py
    ├── test_voice_transcrito_e_processado
    ├── test_audio_file_transcrito
    └── test_regressão_texto_nao_afetado
```

---

## Ordem de Implementação

```
1.  Branch: fase-18
2.  Migração Alembic: tabela audio_config
3.  audio/models.py + audio/schemas.py
4.  🔴 RED: test_audio_service.py (resolver_config)
5.  🟢 GREEN: audio/services.py → AudioService.resolver_config()
6.  🔴 RED: test_stt_providers.py
7.  🟢 GREEN: audio/stt/faster_whisper.py + openai_whisper.py
8.  🔴 RED: test_tts_providers.py
9.  🟢 GREEN: audio/tts/piper.py + openai_tts.py + elevenlabs.py
10. 🟢 AudioService.transcrever() + AudioService.sintetizar()
11. audio/router.py — endpoints CRUD de config
12. api.py → registrar router
13. 🔴 RED: test_webhook_whatsapp_audio.py
14. 🟢 GREEN: whatsapp/router.py → _processar_mensagem_whatsapp()
         whatsapp/client.py → enviar_audio()
15. 🔴 RED: test_webhook_telegram_audio.py
16. 🟢 GREEN: telegram/router.py + telegram/client.py
17. Dockerfile: ffmpeg + pré-download modelos
18. Frontend: AudioConfigForm.vue → SettingsView + AgenteFormView
19. Regressão: todos os testes anteriores passando
```

---

## Gotchas

- **Singleton do WhisperModel:** carrega o modelo na primeira chamada e reutiliza. Modelos grandes (`large-v3`) usam ~3GB RAM — checar recursos do servidor antes de habilitar.
- **Piper via subprocess:** roda como processo filho — usar `asyncio.create_subprocess_exec` para não bloquear o event loop.
- **Conversão de formato:** Piper gera WAV, WhatsApp/Telegram esperam OGG/OPUS. ffmpeg é obrigatório no container.
- **WhatsApp audioMessage:** a Evolution API retorna a mídia como base64 ou URL temporária dependendo da configuração — checar qual formato está vindo no webhook do ambiente.
- **Telegram getFile:** `file_path` expira após 1h — baixar imediatamente ao receber o webhook.
- **elevenlabs_api_key em plaintext:** criptografar com Fernet antes de salvar (igual ao que faremos com `llm_api_key` na Fase 20 de segurança).
- **TTS em português:** Piper `pt_BR-faber-medium` é boa escolha. OpenAI TTS não tem voz PT-BR nativa mas `nova` / `shimmer` entendem português bem.
- **Mensagens de grupo no WhatsApp:** podem conter áudio — respeitar a lógica de `ptt=true` (push-to-talk = voz) vs `ptt=false` (arquivo de áudio) se quiser filtrar só mensagens de voz.
