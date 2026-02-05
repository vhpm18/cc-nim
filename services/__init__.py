"""
Service layer for voice transcription and audio processing.

This package contains services for:
- Audio transcription using Whisper
- Telegram audio downloads
- Voice message processing
"""

from .transcription import TranscriptionService
from .telegram_audio import TelegramAudioDownloader

__all__ = ['TranscriptionService', 'TelegramAudioDownloader']
