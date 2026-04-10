"""
TDD — Providers TTS (Text-to-Speech)

- PiperTTS: subprocess async, converte WAV → OGG/OPUS via ffmpeg
- OpenAITTS: chamada httpx mockada
- ElevenLabsTTS: chamada httpx mockada
- AudioService.sintetizar(): delega ao provider correto
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import types


# ── PiperTTS ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_piper_sintetiza_retorna_bytes_ogg():
    """PiperTTS.sintetizar() retorna bytes OGG após pipeline piper | ffmpeg."""
    from docagent.audio.tts.piper import PiperTTS

    ogg_bytes = b"OGG_FAKE_BYTES"

    mock_piper = AsyncMock()
    mock_piper.stdin = AsyncMock()
    mock_piper.communicate = AsyncMock(return_value=(b"WAV_FAKE_BYTES", b""))
    mock_piper.returncode = 0

    mock_ffmpeg = AsyncMock()
    mock_ffmpeg.communicate = AsyncMock(return_value=(ogg_bytes, b""))
    mock_ffmpeg.returncode = 0

    with patch(
        "docagent.audio.tts.piper.asyncio.create_subprocess_exec",
        side_effect=[mock_piper, mock_ffmpeg],
    ):
        tts = PiperTTS()
        resultado = await tts.sintetizar("Olá mundo", "pt_BR-faber-medium")

    assert resultado == ogg_bytes


@pytest.mark.asyncio
async def test_piper_falha_graciosamente_se_binario_ausente():
    """PiperTTS sem binário piper deve levantar RuntimeError amigável."""
    from docagent.audio.tts.piper import PiperTTS

    with patch(
        "docagent.audio.tts.piper.asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("piper: command not found"),
    ):
        tts = PiperTTS()
        with pytest.raises(RuntimeError, match="piper"):
            await tts.sintetizar("Olá", "pt_BR-faber-medium")


# ── OpenAITTS ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_openai_tts_retorna_bytes_audio():
    """OpenAITTS.sintetizar() faz POST para OpenAI e retorna bytes de áudio."""
    from docagent.audio.tts.openai_tts import OpenAITTS

    audio_bytes = b"MP3_FAKE_BYTES"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = audio_bytes
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("docagent.audio.tts.openai_tts.httpx.AsyncClient", return_value=mock_client):
        tts = OpenAITTS()
        resultado = await tts.sintetizar("Olá mundo", "nova", "sk-test-key")

    assert resultado == audio_bytes
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert "nova" in str(call_kwargs)


@pytest.mark.asyncio
async def test_openai_tts_sem_api_key_levanta_erro():
    """OpenAITTS sem api_key deve levantar ValueError."""
    from docagent.audio.tts.openai_tts import OpenAITTS

    tts = OpenAITTS()
    with pytest.raises(ValueError, match="api_key"):
        await tts.sintetizar("Olá", "nova", "")


# ── ElevenLabsTTS ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_elevenlabs_tts_retorna_bytes_audio():
    """ElevenLabsTTS.sintetizar() faz POST para ElevenLabs e retorna bytes."""
    from docagent.audio.tts.elevenlabs import ElevenLabsTTS

    audio_bytes = b"ELEVENLABS_FAKE_BYTES"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = audio_bytes
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("docagent.audio.tts.elevenlabs.httpx.AsyncClient", return_value=mock_client):
        tts = ElevenLabsTTS()
        resultado = await tts.sintetizar("Olá mundo", "voice-id-123", "el-api-key")

    assert resultado == audio_bytes


@pytest.mark.asyncio
async def test_elevenlabs_tts_sem_voice_id_levanta_erro():
    """ElevenLabsTTS sem voice_id deve levantar ValueError."""
    from docagent.audio.tts.elevenlabs import ElevenLabsTTS

    tts = ElevenLabsTTS()
    with pytest.raises(ValueError, match="voice_id"):
        await tts.sintetizar("Olá", "", "el-api-key")


@pytest.mark.asyncio
async def test_elevenlabs_tts_sem_api_key_levanta_erro():
    """ElevenLabsTTS sem api_key deve levantar ValueError."""
    from docagent.audio.tts.elevenlabs import ElevenLabsTTS

    tts = ElevenLabsTTS()
    with pytest.raises(ValueError, match="api_key"):
        await tts.sintetizar("Olá", "voice-id-123", "")


# ── AudioService.sintetizar() ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audio_service_sintetizar_delega_piper():
    """AudioService.sintetizar() com provider=piper delega ao PiperTTS."""
    from docagent.audio.services import AudioService
    from docagent.audio.models import TtsProvider

    config = types.SimpleNamespace(
        tts_provider=TtsProvider.PIPER.value,
        piper_voz="pt_BR-faber-medium",
        openai_tts_voz="nova",
        elevenlabs_voice_id=None,
        elevenlabs_api_key=None,
    )

    ogg_bytes = b"OGG_BYTES"
    mock_piper_proc = AsyncMock()
    mock_piper_proc.communicate = AsyncMock(return_value=(b"WAV", b""))
    mock_piper_proc.returncode = 0
    mock_ffmpeg_proc = AsyncMock()
    mock_ffmpeg_proc.communicate = AsyncMock(return_value=(ogg_bytes, b""))
    mock_ffmpeg_proc.returncode = 0

    with patch(
        "docagent.audio.tts.piper.asyncio.create_subprocess_exec",
        side_effect=[mock_piper_proc, mock_ffmpeg_proc],
    ):
        resultado = await AudioService.sintetizar("texto", config)

    assert resultado == ogg_bytes


@pytest.mark.asyncio
async def test_audio_service_sintetizar_delega_openai():
    """AudioService.sintetizar() com provider=openai delega ao OpenAITTS."""
    from docagent.audio.services import AudioService
    from docagent.audio.models import TtsProvider

    config = types.SimpleNamespace(
        tts_provider=TtsProvider.OPENAI.value,
        openai_tts_voz="nova",
        elevenlabs_voice_id=None,
        elevenlabs_api_key=None,
    )

    audio_bytes = b"MP3_BYTES"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = audio_bytes
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("docagent.audio.tts.openai_tts.httpx.AsyncClient", return_value=mock_client):
        resultado = await AudioService.sintetizar("texto", config, openai_api_key="sk-test")

    assert resultado == audio_bytes


@pytest.mark.asyncio
async def test_audio_service_sintetizar_delega_elevenlabs():
    """AudioService.sintetizar() com provider=elevenlabs delega ao ElevenLabsTTS."""
    from docagent.audio.services import AudioService
    from docagent.audio.models import TtsProvider

    config = types.SimpleNamespace(
        tts_provider=TtsProvider.ELEVENLABS.value,
        elevenlabs_voice_id="voice-123",
        elevenlabs_api_key="el-key-plaintext",
        openai_tts_voz="nova",
    )

    audio_bytes = b"EL_BYTES"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = audio_bytes
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("docagent.audio.tts.elevenlabs.httpx.AsyncClient", return_value=mock_client):
        resultado = await AudioService.sintetizar("texto", config)

    assert resultado == audio_bytes
