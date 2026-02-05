"""
Transcription service using OpenAI Whisper.

Handles audio transcription with support for multiple languages
and GPU acceleration when available.
"""

import os
from typing import Optional
import asyncio
import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Service for transcribing audio files using Faster Whisper.

    Uses CTranslate2-based implementation for faster inference
    and lower memory usage.
    """

    def __init__(self, model: str = "base", device: str = "auto"):
        """
        Initialize transcription service.

        Args:
            model: Whisper model size (tiny, base, small, medium, large-v3)
            device: Device to use (auto, cpu, cuda)
        """
        self.model_name = model

        # Resolve 'auto' device
        if device == "auto":
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self._model = None
        self._lock = asyncio.Lock()

        logger.info(
            f"TranscriptionService initialized (model: {model}, device: {self.device}, compute: {self.compute_type})"
        )

    @property
    def model(self):
        """Lazy load the Faster Whisper model"""
        if self._model is None:
            logger.info(f"Loading Faster Whisper model '{self.model_name}' on {self.device}...")
            try:
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info("Faster Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Faster Whisper model: {e}")
                raise
        return self._model

    async def transcribe(
        self,
        audio_path: str,
        language: str = "auto",
        initial_prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio file to text using Faster Whisper.

        Args:
            audio_path: Path to audio file
            language: Language code (auto, es, en, etc.)
            initial_prompt: Optional prompt to guide transcription

        Returns:
            Transcribed text
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing audio: {audio_path} (language: {language})")

        loop = asyncio.get_event_loop()

        def _transcribe():
            """Blocking transcription function"""
            try:
                options = {
                    "language": None if language == "auto" else language,
                    "initial_prompt": initial_prompt,
                    "beam_size": 5
                }

                segments, info = self.model.transcribe(audio_path, **options)

                # Segments is a generator, must iterate to process
                text_segments = [segment.text for segment in segments]
                full_text = " ".join(text_segments).strip()

                logger.info(f"Transcription completed: {len(full_text)} chars (detected language: {info.language})")
                return full_text

            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                raise

        # Run in thread pool
        async with self._lock:
            text = await loop.run_in_executor(None, _transcribe)

        return text

    async def cleanup(self):
        """Cleanup model resources"""
        if self._model is not None:
            logger.info("Cleaning up Whisper model")
            self._model = None
