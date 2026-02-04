"""Tests for messaging models."""

import pytest
from messaging.models import IncomingMessage


def test_incoming_message_with_voice_file_id():
    """Test IncomingMessage with voice_file_id field."""
    # Arrange & Act
    message = IncomingMessage(
        text="",
        voice_file_id="voice_123",
        chat_id="123",
        user_id="456",
        message_id="789",
        platform="telegram",
        reply_to_message_id=None,
        raw_event=None
    )

    # Assert
    assert message.voice_file_id == "voice_123"
    assert message.text == ""


def test_incoming_message_without_voice_file_id():
    """Test IncomingMessage without voice_file_id (default None)."""
    # Arrange & Act
    message = IncomingMessage(
        text="Hola",
        chat_id="123",
        user_id="456",
        message_id="789",
        platform="telegram"
    )

    # Assert
    assert message.voice_file_id is None
    assert message.text == "Hola"


def test_incoming_message_is_reply():
    """Test is_reply method with voice message."""
    # Arrange
    message = IncomingMessage(
        text="",
        voice_file_id="voice_123",
        chat_id="123",
        user_id="456",
        message_id="789",
        platform="telegram",
        reply_to_message_id="456"
    )

    # Act & Assert
    assert message.is_reply() is True
