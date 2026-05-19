# Módulo: audio/

**Path:** `src/docagent/audio/`
**Fase:** 18
**Status:** Implementado (Sprint 8 pendente — Dockerfile + regressão)

---

## Responsabilidade

Configuração, transcrição (STT) e síntese (TTS) de áudio para os canais WhatsApp e Telegram.

---

## Estrutura

```
audio/
├── models.py       — AudioConfig ORM, SttProvider, TtsProvider, ModoResposta
├── schemas.py      — AudioConfigPublic, AudioConfigUpdate
├── services.py     — AudioService
├── router.py       — 5 endpoints REST
├── stt/
│   ├── faster_whisper.py  — FasterWhisperSTT (singleton)
│   └── openai_whisper.py  — OpenAIWhisperSTT
└── tts/
    ├── piper.py           — PiperTTS (subprocess + ffmpeg)
    ├── openai_tts.py      — OpenAITTS
    └── elevenlabs.py      — ElevenLabsTTS
```

---

## Modelo: AudioConfig

```python
__tablename__ = "audio_config"

tenant_id: FK → tenant (NOT NULL)
agente_id: FK → agente (nullable)   # NULL = config padrão do tenant
UniqueConstraint("tenant_id", "agente_id")
```

**Campos STT:** `stt_habilitado`, `stt_provider`, `stt_modelo`
**Campos TTS:** `tts_habilitado`, `tts_provider`, `piper_voz`, `openai_tts_voz`, `elevenlabs_voice_id`, `elevenlabs_api_key`
**Modo:** `modo_resposta` (audio_apenas | texto_apenas | audio_e_texto)

---

## Cascata de Configuração

```
1. Agente tem AudioConfig própria?  → usa ela
2. Tenant tem AudioConfig padrão?   → usa ela (agente_id IS NULL)
3. Nenhuma                          → types.SimpleNamespace (system defaults hardcoded)
```

System defaults: `stt_habilitado=False`, `tts_habilitado=False`, `stt_modelo="small"`, `tts_provider="piper"`.
(Fase 21: modelo padrão atualizado de `"base"` para `"small"` — melhor qualidade para português.)

**Importante:** system defaults retornam `SimpleNamespace`, não objeto ORM. `id=None` nesse caso.
Ver [decisao: system-defaults-simplenamespace](../decisoes/system-defaults-simplenamespace.md).

---

## Endpoints REST

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/api/audio-config/default` | Config padrão do tenant |
| PUT | `/api/audio-config/default` | Salva/atualiza config padrão |
| GET | `/api/agentes/{id}/audio-config` | Config do agente (404 se não existe) |
| PUT | `/api/agentes/{id}/audio-config` | Upsert config do agente |
| DELETE | `/api/agentes/{id}/audio-config` | Remove override → volta ao padrão |

`elevenlabs_api_key` nunca é retornada nas respostas (write-only).

---

## STT — FasterWhisperSTT

- **Singleton:** `_model: ClassVar = None` — carregado uma vez, reutilizado
- **Thread:** `asyncio.to_thread(_transcrever_sync)` — não bloqueia event loop
- **Modelo:** `WhisperModel(modelo, device="cpu", compute_type="int8")`
- **Modelos disponíveis:** `tiny | base | small | medium | large-v3`
- **Gotcha:** `large-v3` usa ~3GB RAM

---

## TTS — PiperTTS

- **Pipeline:** `piper --model {voz} --output-raw` → pipe WAV → `ffmpeg -f s16le -ar 22050 -ac 1 -i pipe:0 -c:a libopus -b:a 64k -f ogg pipe:1`
- **Output:** bytes OGG/OPUS (compatível WhatsApp + Telegram)
- **Gotcha:** `ffmpeg` precisa estar instalado no container (falta no Dockerfile atual — Sprint 8)
- **Voz recomendada para pt-BR:** `pt_BR-faber-medium`

---

## Frontend

- `frontend/src/api/audioClient.ts` — funções `getDefault`, `saveDefault`, `getAgente`, `saveAgente`, `deleteAgente`
- `frontend/src/components/AudioConfigForm.vue` — componente reutilizável
- `SettingsView.vue` → aba "Áudio" (config padrão do tenant)
- `AgenteFormView.vue` → card "Configuração de Áudio" (config específica do agente, só no modo edição)
