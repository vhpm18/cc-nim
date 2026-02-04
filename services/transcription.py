"""
Transcription service using OpenAI Whisper.

Handles audio transcription with support for multiple languages
and GPU acceleration when available.
"""

import os
import whisper
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Service for transcribing audio files using Whisper.

    Uses OpenAI's Whisper model for automatic speech recognition.
    Supports GPU acceleration when CUDA is available.
    """

    def __init__(self, model: str = "base", device: str = "auto"):
        """
        Initialize transcription service.

        Args:
            model: Whisper model size (tiny, base, small, medium, large, large-v3)
            device: Device to use (auto, cpu, cuda)
        """
        self.model_name = model
        self.device = device
        self._model = None
        self._lock = asyncio.Lock()
        logger.info(
            f"TranscriptionService initialized (model: {model}, device: {device})"
        )

    @property
    def model(self):
        """Lazy load the Whisper model"""
        if self._model is None:
            logger.info(f"Loading Whisper model '{self.model_name}' on device '{self.device}'")
            self._model = whisper.load_model(
                self.model_name,
                device=self.device
            )
            logger.info("Whisper model loaded successfully")
        return self._model

    async def transcribe(
        self,
        audio_path: str,
        language: str = "auto",
        initial_prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio file to text using Whisper.

        Args:
            audio_path: Path to audio file (mp3, wav, m4a, ogg, etc.)
            language: Language code (auto, es, en, etc.)
            initial_prompt: Optional prompt to guide transcription

        Returns:
            Transcribed text

        Raises:
            FileNotFoundError: If audio file doesn't exist
            Exception: If transcription fails
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing audio: {audio_path} (language: {language})")

        loop = asyncio.get_event_loop()

        def _transcribe():
            """Blocking transcription function to run in executor"""
            try:
                options = {
                    "language": None if language == "auto" else language,
                    "initial_prompt": initial_prompt
                }

                result = self.model.transcribe(audio_path, **options)
                text = result["text"].strip()

                logger.info(f"Transcription completed: {len(text)} characters")
                return text

            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                raise

        # Run in thread pool to avoid blocking the event loop
        async with self._lock:
            text = await loop.run_in_executor(None, _transcribe)

        return text

    async def cleanup(self):
        """Cleanup model resources"""
        if self._model is not None:
            logger.info("Cleaning up Whisper model")
            self._model = None
