"""
Testes de integração do pipeline de áudio — sem mocks, binários reais.

Requerem faster-whisper e piper instalados (Sprint 8).
Marcados com @pytest.mark.integration para separar do CI rápido.

Executar com:
    uv run pytest tests/test_audio/test_pipeline_integration.py -v
"""
import types
import pytest

from docagent.audio.tts.piper import PiperTTS
from docagent.audio.stt.faster_whisper import FasterWhisperSTT
from docagent.audio.services import AudioService


# ── TTS real ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_piper_gera_ogg_bytes_reais():
    """PiperTTS gera bytes OGG não-vazios com voz real."""
    tts = PiperTTS()
    resultado = await tts.sintetizar("Olá, teste de integração.", "pt_BR-faber-medium")
    assert isinstance(resultado, bytes)
    assert len(resultado) > 1000  # OGG real tem pelo menos 1 KB


@pytest.mark.asyncio
@pytest.mark.integration
async def test_piper_textos_diferentes_geram_audios_diferentes():
    """Textos distintos produzem áudios distintos."""
    tts = PiperTTS()
    a1 = await tts.sintetizar("Bom dia.", "pt_BR-faber-medium")
    a2 = await tts.sintetizar("Boa noite, como vai?", "pt_BR-faber-medium")
    assert a1 != a2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_piper_modelo_inexistente_levanta_runtime_error():
    """Modelo que não existe retorna RuntimeError claro."""
    tts = PiperTTS()
    with pytest.raises(RuntimeError, match="piper"):
        await tts.sintetizar("teste", "modelo_que_nao_existe")


# ── STT real ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_faster_whisper_transcreve_audio_real():
    """FasterWhisperSTT transcreve áudio gerado pelo Piper."""
    tts = PiperTTS()
    stt = FasterWhisperSTT()

    ogg = await tts.sintetizar("Olá, como posso te ajudar?", "pt_BR-faber-medium")
    texto = await stt.transcrever(ogg, "base")

    assert isinstance(texto, str)
    assert len(texto.strip()) > 0
    # Whisper deve reconhecer pelo menos parte do texto
    assert any(w in texto.lower() for w in ["olá", "ola", "como", "ajudar", "posso"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_faster_whisper_singleton_nao_recarrega_modelo():
    """Modelo Whisper é carregado uma vez e reutilizado."""
    stt = FasterWhisperSTT()
    tts = PiperTTS()
    ogg = await tts.sintetizar("teste singleton", "pt_BR-faber-medium")

    # Primeira chamada — carrega o modelo
    FasterWhisperSTT._model = None
    await stt.transcrever(ogg, "base")
    modelo_apos_primeira = FasterWhisperSTT._model

    # Segunda chamada — reutiliza
    await stt.transcrever(ogg, "base")
    modelo_apos_segunda = FasterWhisperSTT._model

    assert modelo_apos_primeira is modelo_apos_segunda


@pytest.mark.asyncio
@pytest.mark.integration
async def test_faster_whisper_audio_vazio_retorna_string():
    """Áudio vazio/silêncio não levanta exceção — retorna string (pode ser vazia)."""
    stt = FasterWhisperSTT()
    # 1 segundo de silêncio em PCM raw (zeros) → convertido para OGG vazio
    import subprocess, tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        tmp = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
             "-t", "1", "-c:a", "libopus", tmp, "-y", "-loglevel", "error"],
            check=True
        )
        with open(tmp, "rb") as f:
            silencio = f.read()
    finally:
        os.unlink(tmp)

    resultado = await stt.transcrever(silencio, "base")
    assert isinstance(resultado, str)


# ── Ciclo completo TTS → STT ─────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_ciclo_completo_tts_para_stt():
    """Pipeline completo: texto → Piper (TTS) → Whisper (STT) → texto."""
    frase = "Quais são os planos disponíveis?"
    tts = PiperTTS()
    stt = FasterWhisperSTT()

    ogg = await tts.sintetizar(frase, "pt_BR-faber-medium")
    transcrito = await stt.transcrever(ogg, "base")

    # Whisper não precisa ser 100% exato — verifica palavras-chave
    palavras_chave = ["planos", "disponíveis", "quais", "são"]
    acertos = sum(1 for p in palavras_chave if p in transcrito.lower())
    assert acertos >= 2, f"Transcrição muito diferente do original: '{transcrito}'"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ciclo_audio_service_config_real():
    """AudioService.transcrever + sintetizar com config real (sem banco)."""
    config = types.SimpleNamespace(
        stt_habilitado=True,
        stt_provider="faster_whisper",
        stt_modelo="base",
        tts_habilitado=True,
        tts_provider="piper",
        piper_voz="pt_BR-faber-medium",
        openai_tts_voz="nova",
        elevenlabs_voice_id=None,
        elevenlabs_api_key=None,
        modo_resposta="audio_e_texto",
    )
    svc = AudioService()
    tts = PiperTTS()

    # Gera áudio de entrada
    audio_entrada = await tts.sintetizar("Olá, preciso de ajuda.", "pt_BR-faber-medium")

    # STT
    texto = await svc.transcrever(audio_entrada, config)
    assert len(texto.strip()) > 0

    # TTS da resposta
    resposta = "Olá! Estou aqui para ajudar."
    audio_saida = await svc.sintetizar(resposta, config)
    assert isinstance(audio_saida, bytes)
    assert len(audio_saida) > 1000


# ── Fidelidade de transcrição ─────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("frase,palavras_esperadas", [
    ("bom dia", ["bom", "dia"]),
    ("qual é o seu nome", ["qual", "nome"]),
    ("preciso de suporte técnico", ["suporte", "técnico", "preciso"]),
    ("obrigado pela ajuda", ["obrigado", "ajuda"]),
])
async def test_transcricao_frases_comuns(frase, palavras_esperadas):
    """Frases comuns de atendimento são transcritas com pelo menos 50% de acerto."""
    tts = PiperTTS()
    stt = FasterWhisperSTT()

    ogg = await tts.sintetizar(frase, "pt_BR-faber-medium")
    transcrito = await stt.transcrever(ogg, "base")

    acertos = sum(1 for p in palavras_esperadas if p in transcrito.lower())
    assert acertos >= len(palavras_esperadas) // 2 + 1, (
        f"Transcrição '{transcrito}' perdeu muitas palavras de '{frase}'"
    )
