"""Tests for VoiceProcessor."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from messaging.voice_processor import VoiceProcessor
from messaging.models import IncomingMessage


@pytest.fixture
def mock_bot():
    """Mock Telegram bot with async methods."""
    bot = MagicMock()
    bot.get_file = AsyncMock()
    return bot


@pytest.fixture
def mock_services():
    """Mock transcription and audio services."""
    with patch('services.telegram_audio.TelegramAudioDownloader') as mock_downloader_class, \
         patch('services.transcription.TranscriptionService') as mock_transcription_class, \
         patch('services.telegram_audio.AudioSegment') as mock_audio_module, \
         patch('services.telegram_audio.PYDUB_AVAILABLE', True), \
         patch('services.telegram_audio.os.makedirs'), \
         patch('services.telegram_audio.os.unlink'):

        # Mock transcription service
        mock_transcription_instance = MagicMock()
        mock_transcription_instance.transcribe = AsyncMock(return_value="Texto transcrito")
        mock_transcription_class.return_value = mock_transcription_instance

        # Mock downloader - IMPORTANT: download_voice must return a VALID path
        mock_downloader_instance = MagicMock()
        mock_downloader_instance.download_voice = AsyncMock(return_value="/tmp/test.mp3")
        mock_downloader_instance.download_and_transcribe = AsyncMock(return_value="Texto transcrito")
        mock_downloader_class.return_value = mock_downloader_instance

        # Mock pydub AudioSegment
        mock_audio = MagicMock()
        mock_audio.export = MagicMock()
        mock_audio_module.from_ogg = MagicMock(return_value=mock_audio)
        mock_audio_module.from_mp3 = MagicMock(return_value=mock_audio)

        yield {
            'transcription': mock_transcription_class,
            'downloader': mock_downloader_class,
            'transcription_instance': mock_transcription_instance,
            'downloader_instance': mock_downloader_instance
        }


@pytest.mark.asyncio
async def test_process_message_with_voice_file_id(mock_bot, mock_services):
    """Test processing message with voice file ID."""
    processor = VoiceProcessor(get_bot=lambda: mock_bot)

    incoming = IncomingMessage(
        text="",
        voice_file_id="voice_123",
        chat_id="123",
        user_id="456",
        message_id="789",
        platform="telegram",
        raw_event=None
    )

    processed = await processor.process_message(incoming)

    assert processed.text == "Texto transcrito"
    assert processed.voice_file_id == "voice_123"
    assert processed.chat_id == incoming.chat_id
    assert processed.user_id == incoming.user_id
    assert processed.platform == incoming.platform
    mock_services['downloader_instance'].download_and_transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_without_voice():
    """Test processing message without voice file ID (pass-through)."""
    processor = VoiceProcessor()
    incoming = IncomingMessage(
        text="Hola mundo",
        voice_file_id=None,
        chat_id="123",
        user_id="456",
        message_id="789",
        platform="telegram",
        raw_event=None
    )
    processed = await processor.process_message(incoming)
    assert processed.text == "Hola mundo"
    assert processed.voice_file_id is None


@pytest.mark.asyncio
async def test_process_message_voice_transcription_failed(mock_bot):
    """Test handling transcription failure."""
    processor = VoiceProcessor(get_bot=lambda: mock_bot)
    incoming = IncomingMessage(
        text="",
        voice_file_id="voice_123",
        chat_id="123",
        user_id="456",
        message_id="789",
        platform="telegram",
        raw_event=None
    )

    with patch('services.telegram_audio.TelegramAudioDownloader') as mock_downloader_class:
        mock_downloader_instance = MagicMock()
        mock_downloader_instance.download_and_transcribe = AsyncMock(
            side_effect=RuntimeError("Transcription failed")
        )
        mock_downloader_instance.download_voice = AsyncMock(return_value="/tmp/test.ogg")
        mock_downloader_class.return_value = mock_downloader_instance

        with pytest.raises(RuntimeError, match="Failed to transcribe voice message"):
            await processor.process_message(incoming)


@pytest.mark.asyncio
async def test_initialize_with_get_bot():
    """Test initialization with bot getter."""
    mock_bot = Mock()
    processor = VoiceProcessor(get_bot=lambda: mock_bot)
    incoming = IncomingMessage(
        text="",
        voice_file_id="voice_123",
        chat_id="123",
        user_id="456",
        message_id="789",
        platform="telegram",
        raw_event=None
    )

    with patch('services.telegram_audio.TelegramAudioDownloader') as mock_dl_class, \
         patch('services.transcription.TranscriptionService') as mock_trans_class, \
         patch.object(processor, 'process_message', AsyncMock(return_value=incoming)):
        await processor.process_message(incoming)


@pytest.mark.asyncio
async def test_cleanup():
    """Test cleanup of resources."""
    processor = VoiceProcessor()
    mock_downloader = Mock()
    mock_downloader.cleanup = AsyncMock()
    processor.audio_downloader = mock_downloader
    await processor.cleanup()
    mock_downloader.cleanup.assert_called_once()
