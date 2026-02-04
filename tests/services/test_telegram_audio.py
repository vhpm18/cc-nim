"""Tests for TelegramAudioDownloader."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from services.telegram_audio import TelegramAudioDownloader


@pytest.fixture
def mock_bot():
    """Mock Telegram Bot"""
    bot = Mock()
    bot.get_file = AsyncMock()
    return bot


@pytest.fixture
def downloader(mock_bot):
    """Create TelegramAudioDownloader instance"""
    return TelegramAudioDownloader(bot=mock_bot)


@pytest.mark.asyncio
async def test_download_voice_message(downloader, mock_bot, tmp_path):
    """Test successful download of voice message"""
    # Arrange
    mock_file = Mock()
    mock_file.file_path = "voice/file_123.ogg"
    mock_file.download_to_drive = AsyncMock()
    mock_bot.get_file.return_value = mock_file

    # Mock pydub
    mock_audio = MagicMock()
    mock_audio.export = Mock()

    with patch('services.telegram_audio.os.makedirs'), \
         patch('services.telegram_audio.os.unlink') as mock_unlink, \
         patch('services.telegram_audio.AudioSegment.from_ogg', return_value=mock_audio):

        # Act
        result = await downloader.download_voice(
            file_id="file_unique_id_123",
            output_dir=str(tmp_path)
        )

        # Assert
        assert result.endswith('.mp3')
        mock_bot.get_file.assert_called_once_with("file_unique_id_123")


@pytest.mark.asyncio
async def test_download_voice_pydub_unavailable(downloader, mock_bot, tmp_path):
    """Test download when pydub is not available"""
    # Arrange
    mock_file = Mock()
    mock_file.file_path = "voice/file_123.ogg"
    mock_file.download_to_drive = AsyncMock()  # Make it async
    mock_bot.get_file.return_value = mock_file

    with patch('services.telegram_audio.PYDUB_AVAILABLE', False), \
         patch('services.telegram_audio.os.makedirs'):

        # Act
        result = await downloader.download_voice(
            file_id="file_id_123",
            output_dir=str(tmp_path)
        )

        # Assert - Should return OGG file directly
        assert result.endswith('.ogg')


@pytest.mark.asyncio
async def test_download_and_transcribe(downloader, mock_bot):
    """Test download and transcribe integration"""
    # Arrange
    mock_file = Mock()
    mock_file.file_path = "voice/test.ogg"
    mock_file.download_to_drive = AsyncMock()  # Make it async
    mock_bot.get_file.return_value = mock_file

    mock_transcription_service = Mock()
    mock_transcription_service.transcribe = AsyncMock(
        return_value="Texto transcrito"
    )

    # Mock pydub
    mock_audio = MagicMock()
    mock_audio.export = Mock()

    with patch('services.telegram_audio.os.makedirs'), \
         patch('services.telegram_audio.os.unlink') as mock_unlink, \
         patch('services.telegram_audio.AudioSegment.from_ogg', return_value=mock_audio):

        # Act
        result = await downloader.download_and_transcribe(
            file_id="file_123",
            transcription_service=mock_transcription_service,
            output_dir="./tests/data",
            language="spanish"
        )

        # Assert
        assert result == "Texto transcrito"
        mock_transcription_service.transcribe.assert_called_once()
