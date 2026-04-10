"""
TDD — Providers STT (Speech-to-Text)

- FasterWhisperSTT: singleton do modelo, transcrição via to_thread
- OpenAIWhisperSTT: chamada httpx mockada
- AudioService.transcrever(): delega ao provider correto
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import types


# ── FasterWhisperSTT ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_faster_whisper_transcreve_audio():
    """FasterWhisperSTT.transcrever() retorna texto dos segmentos."""
    from docagent.audio.stt.faster_whisper import FasterWhisperSTT

    seg1 = MagicMock()
    seg1.text = "Olá, "
    seg2 = MagicMock()
    seg2.text = "mundo."
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([seg1, seg2], MagicMock())

    with patch("docagent.audio.stt.faster_whisper.FasterWhisperSTT.get_model", return_value=mock_model):
        stt = FasterWhisperSTT()
        resultado = await stt.transcrever(b"audio-bytes", "base")

    assert resultado == "Olá, mundo."
    mock_model.transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_faster_whisper_singleton_carrega_uma_vez():
    """get_model() deve instanciar WhisperModel apenas uma vez."""
    from docagent.audio.stt.faster_whisper import FasterWhisperSTT

    # Reseta singleton antes do teste
    FasterWhisperSTT._model = None

    with patch("docagent.audio.stt.faster_whisper.WhisperModel") as mock_cls:
        mock_cls.return_value = MagicMock()
        m1 = FasterWhisperSTT.get_model("base")
        m2 = FasterWhisperSTT.get_model("base")

    assert m1 is m2
    mock_cls.assert_called_once_with("base", device="cpu", compute_type="int8")

    # Limpa após o teste
    FasterWhisperSTT._model = None


@pytest.mark.asyncio
async def test_faster_whisper_audio_vazio_retorna_string_vazia():
    """Áudio sem segmentos → retorna string vazia."""
    from docagent.audio.stt.faster_whisper import FasterWhisperSTT

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())

    with patch("docagent.audio.stt.faster_whisper.FasterWhisperSTT.get_model", return_value=mock_model):
        stt = FasterWhisperSTT()
        resultado = await stt.transcrever(b"", "base")

    assert resultado == ""


# ── OpenAIWhisperSTT ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_openai_whisper_transcreve_audio():
    """OpenAIWhisperSTT.transcrever() faz POST para OpenAI e retorna texto."""
    from docagent.audio.stt.openai_whisper import OpenAIWhisperSTT

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "Texto transcrito via OpenAI"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("docagent.audio.stt.openai_whisper.httpx.AsyncClient", return_value=mock_client):
        stt = OpenAIWhisperSTT()
        resultado = await stt.transcrever(b"audio-bytes", "sk-test-key")

    assert resultado == "Texto transcrito via OpenAI"


@pytest.mark.asyncio
async def test_openai_whisper_sem_api_key_levanta_erro():
    """OpenAIWhisperSTT sem api_key deve levantar ValueError."""
    from docagent.audio.stt.openai_whisper import OpenAIWhisperSTT

    stt = OpenAIWhisperSTT()
    with pytest.raises(ValueError, match="api_key"):
        await stt.transcrever(b"audio-bytes", "")


# ── AudioService.transcrever() ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audio_service_transcrever_delega_faster_whisper():
    """AudioService.transcrever() com provider=faster_whisper delega ao FasterWhisperSTT."""
    from docagent.audio.services import AudioService
    from docagent.audio.models import SttProvider

    config = types.SimpleNamespace(
        stt_provider=SttProvider.FASTER_WHISPER.value,
        stt_modelo="base",
    )

    with patch("docagent.audio.stt.faster_whisper.FasterWhisperSTT.get_model") as mock_get:
        seg = MagicMock()
        seg.text = "Texto do faster-whisper"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg], MagicMock())
        mock_get.return_value = mock_model

        resultado = await AudioService.transcrever(b"bytes", config)

    assert resultado == "Texto do faster-whisper"


@pytest.mark.asyncio
async def test_audio_service_transcrever_delega_openai():
    """AudioService.transcrever() com provider=openai delega ao OpenAIWhisperSTT."""
    from docagent.audio.services import AudioService
    from docagent.audio.models import SttProvider

    config = types.SimpleNamespace(
        stt_provider=SttProvider.OPENAI.value,
        stt_modelo="whisper-1",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "Texto do OpenAI"}
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("docagent.audio.stt.openai_whisper.httpx.AsyncClient", return_value=mock_client):
        resultado = await AudioService.transcrever(b"bytes", config, openai_api_key="sk-test")

    assert resultado == "Texto do OpenAI"
