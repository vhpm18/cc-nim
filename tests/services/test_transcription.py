"""Tests for TranscriptionService with Whisper integration."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from services.transcription import TranscriptionService


@pytest.fixture
def mock_whisper():
    """Mock Whisper module"""
    with patch('services.transcription.WhisperModel') as mock_whisper_mod:
        mock_model_instance = MagicMock()
        mock_model_instance.transcribe.return_value = (
            [MagicMock(text='Hola mundo, esta es una prueba de transcripción')],
            MagicMock(language='es')
        )
        mock_whisper_mod.return_value = mock_model_instance
        yield mock_whisper_mod


@pytest.fixture
def transcription_service(mock_whisper):
    """Create TranscriptionService instance"""
    service = TranscriptionService(model="base", device="cpu")
    return service


@pytest.mark.asyncio
async def test_transcribe_audio_file(
    transcription_service, mock_whisper, tmp_path
):
    """Test successful transcription of audio file"""
    # Arrange
    test_audio = tmp_path / "test.mp3"
    test_audio.write_bytes(b"fake audio data")
    expected_text = "Hola mundo, esta es una prueba de transcripción"

    # Act
    result = await transcription_service.transcribe(str(test_audio))

    # Assert
    assert result == expected_text
    mock_whisper.assert_called_once_with("base", device="cpu", compute_type="int8")
    mock_whisper.return_value.transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_spanish_audio(
    transcription_service, mock_whisper, tmp_path
):
    """Test transcription with Spanish language specified"""
    # Arrange
    test_audio = tmp_path / "test.mp3"
    test_audio.write_bytes(b"fake audio data")
    mock_whisper.return_value.transcribe.return_value = (
        [MagicMock(text='Buenos días, me gustaría saber sobre Python')],
        MagicMock(language='es')
    )

    # Act
    result = await transcription_service.transcribe(
        str(test_audio),
        language="spanish"
    )

    # Assert
    assert "Buenos días" in result
    # Verify language parameter was passed
    mock_whisper.return_value.transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_nonexistent_file(transcription_service):
    """Test error handling for non-existent file"""
    # Act & Assert
    with pytest.raises(FileNotFoundError):
        await transcription_service.transcribe("/nonexistent/file.mp3")


@pytest.mark.asyncio
async def test_transcribe_english_audio(
    transcription_service, mock_whisper, tmp_path
):
    """Test transcription of English audio"""
    # Arrange
    test_audio = tmp_path / "test.mp3"
    test_audio.write_bytes(b"fake audio data")
    expected_text = "Hello world, this is a test transcription"
    mock_whisper.return_value.transcribe.return_value = (
        [MagicMock(text=expected_text)],
        MagicMock(language='en')
    )

    # Act
    result = await transcription_service.transcribe(
        str(test_audio),
        language="english"
    )

    # Assert
    assert result == expected_text
