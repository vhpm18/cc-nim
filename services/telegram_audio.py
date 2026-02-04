"""
Telegram audio downloader service.

Handles downloading voice messages and audio files from Telegram,
with automatic format conversion for Whisper compatibility.
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Optional
from telegram import Bot, File
from config import settings

logger = logging.getLogger(__name__)


try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available, audio conversion disabled")


class TelegramAudioDownloader:
    """
    Service for downloading audio files from Telegram.

    Automatically converts OGG files (Telegram's default) to MP3
    for better compatibility with Whisper.
    """

    def __init__(self, bot: Bot):
        """
        Initialize downloader.

        Args:
            bot: Telegram Bot instance
        """
        self.bot = bot
        logger.info("TelegramAudioDownloader initialized")

    async def download_voice(
        self,
        file_id: str,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        Download voice message from Telegram.

        Args:
            file_id: Telegram file_id from voice message
            output_dir: Directory to save the file (default: settings.audio_download_dir)
            filename: Optional custom filename

        Returns:
            Path to downloaded (and converted) audio file

        Raises:
            Exception: If download or conversion fails
        """
        output_dir = output_dir or settings.audio_download_dir
        os.makedirs(output_dir, exist_ok=True)

        if filename is None:
            filename = f"{file_id}.ogg"

        output_path = Path(output_dir) / filename
        logger.info(f"Downloading voice message: {file_id}")

        # Get file info from Telegram
        file: File = await self.bot.get_file(file_id)

        # Download to temporary file first
        with tempfile.NamedTemporaryFile(
            suffix=".ogg",
            delete=False
        ) as temp_file:
            temp_path = temp_file.name

        try:
            # Download the file
            await file.download_to_drive(temp_path)
            logger.info(f"Downloaded to temp file: {temp_path}")

            # Check if pydub is available
            if not PYDUB_AVAILABLE:
                logger.warning("pydub not available, returning OGG file")
                return temp_path

            # Convert to MP3 for better Whisper compatibility
            from pydub import AudioSegment
            audio = AudioSegment.from_ogg(temp_path)

            # Export as MP3
            mp3_path = output_path.with_suffix(".mp3")
            audio.export(mp3_path, format="mp3")
            logger.info(f"Converted to MP3: {mp3_path}")

            return str(mp3_path)

        finally:
            # Cleanup temp OGG file
            if os.path.exists(temp_path) and PYDUB_AVAILABLE:
                os.unlink(temp_path)
                logger.debug(f"Cleaned up temp file: {temp_path}")

    async def download_and_transcribe(
        self,
        file_id: str,
        transcription_service,
        output_dir: Optional[str] = None,
        language: str = "auto"
    ) -> str:
        """
        Download voice and transcribe in one step.

        Args:
            file_id: Telegram file_id
            transcription_service: TranscriptionService instance
            output_dir: Directory for downloads
            language: Language for transcription

        Returns:
            Transcribed text

        Raises:
            Exception: If download or transcription fails
        """
        logger.info(f"Downloading and transcribing: {file_id}")

        # Download audio
        audio_path = await self.download_voice(file_id, output_dir)

        try:
            # Transcribe
            text = await transcription_service.transcribe(
                audio_path,
                language=language
            )
            logger.info(f"Transcription completed: {len(text)} chars")

            # Cleanup audio file after transcription if enabled
            if settings.cleanup_audio_files and os.path.exists(audio_path):
                os.unlink(audio_path)
                logger.debug(f"Cleaned up audio file: {audio_path}")

            return text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            # Cleanup on error too
            if os.path.exists(audio_path):
                os.unlink(audio_path)
            raise
