"""
Voice message processor for automatic transcription and handling.

Integrates Whisper transcription with the message handling pipeline.
"""

import asyncio
import logging
from typing import Optional, Callable

from .models import IncomingMessage
from services.telegram_audio import TelegramAudioDownloader
from services.transcription import TranscriptionService

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """
    Handles automatic processing of voice messages.

    Downloads voice files from Telegram, transcribes them with Whisper,
    and prepares them for Claude processing.
    """

    def __init__(self, get_bot: Optional[Callable] = None):
        """
        Initialize voice processor.

        Args:
            get_bot: Function that returns the Telegram bot instance
        """
        self.audio_downloader: Optional[TelegramAudioDownloader] = None
        self.transcription_service: Optional[TranscriptionService] = None
        self._get_bot = get_bot
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize voice processing services.

        Should be called during startup, not when first needed.
        """
        if self._initialized:
            return

        from config import settings

        # Initialize transcription service with model loading
        logger.info(f"Initializing TranscriptionService (model: {settings.whisper_model})")
        self.transcription_service = TranscriptionService(
            model=settings.whisper_model,
            device=settings.whisper_device
        )
        logger.info("TranscriptionService ready")

        # Initialize audio downloader if bot getter is available
        if self._get_bot:
            bot = self._get_bot()
            if bot:
                from services.telegram_audio import TelegramAudioDownloader

                self.audio_downloader = TelegramAudioDownloader(bot=bot)
                logger.info("TelegramAudioDownloader ready")

        self._initialized = True
        logger.info("VoiceProcessor initialized")

    async def process_message(self, incoming: IncomingMessage) -> IncomingMessage:
        """
        Process an incoming message, transcribing voice if present.

        Args:
            incoming: The incoming message (may have voice_file_id)

        Returns:
            IncomingMessage with text set to transcription if voice was present
        """
        # If no voice file ID, return as-is
        if not incoming.voice_file_id:
            return incoming

        logger.info(f"Processing voice message: file_id={incoming.voice_file_id}")

        # Initialize if needed
        if not self.transcription_service:
            await self.initialize()

        try:
            # Download voice file
            if not self.audio_downloader and self._get_bot:
                bot = self._get_bot()
                if bot:
                    from services.telegram_audio import TelegramAudioDownloader

                    self.audio_downloader = TelegramAudioDownloader(bot=bot)

            if not self.audio_downloader:
                logger.error("No audio downloader available")
                raise RuntimeError("Audio downloader not initialized")

            from config import settings

            # Download and transcribe
            transcription = await self.audio_downloader.download_and_transcribe(
                file_id=incoming.voice_file_id,
                transcription_service=self.transcription_service,
                output_dir=settings.audio_download_dir,
                language=settings.whisper_language
            )

            if not transcription or len(transcription.strip()) < 2:
                raise ValueError("Transcription is too short or empty")

            # Log successful transcription
            preview = transcription[:100] + "..." if len(transcription) > 100 else transcription
            logger.info(f"Voice transcription successful: {len(transcription)} chars - {preview}")

            # Create new IncomingMessage with transcription as text
            # Keep the original voice_file_id for reference
            processed_message = IncomingMessage(
                text=transcription,
                voice_file_id=incoming.voice_file_id,  # Keep original
                chat_id=incoming.chat_id,
                user_id=incoming.user_id,
                message_id=incoming.message_id,
                platform=incoming.platform,
                reply_to_message_id=incoming.reply_to_message_id,
                raw_event=incoming.raw_event,
                timestamp=incoming.timestamp
            )

            return processed_message

        except Exception as e:
            logger.error(f"Voice transcription failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to transcribe voice message: {str(e)}")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.audio_downloader:
            await self.audio_downloader.cleanup()
        logger.info("VoiceProcessor cleanup completed")
