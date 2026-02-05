# Telegram Voice Transcription Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Permitir enviar notas de voz a través de Telegram, transcribirlas automáticamente con Whisper (local), mostrar preview al usuario para confirmación, y luego enviar el texto a Claude Code CLI.

**Architecture:** Integrar Whisper local (modelo small multilingüe) en el pipeline de Telegram. El flujo es: recibir audio → descargar → convertir OGG a WAV → transcribir con Whisper (español) → mostrar preview con botones de confirmación → si confirma, enviar texto a Claude Code.

**Tech Stack:**
- Whisper (openai-whisper) - transcripción local
- ffmpeg - conversión de audio OGG a WAV
- python-telegram-bot - handlers de audio
- pydub - manejo de audio (alternativa a ffmpeg)

---

## Task 1: Instalar dependencias

**Files:**
- Modify: `pyproject.toml`

**Step 1: Agregar dependencias a pyproject.toml** (Paquete correcto: openai-whisper)

```toml
[project]
dependencies = [
    ...
    "openai-whisper>=20230314",
    "ffmpeg-python>=0.2.0",
    "pydub>=0.25.1",
]
```

**Step 2: Instalar dependencias**

```bash
uv sync
```

**Step 3: Verificar instalación**

```bash
uv run python -c "import whisper; print('Whisper installed successfully')"
uv run ffmpeg -version
```

Expected output: Versión de ffmpeg

**Step 4: Descargar modelo Whisper (small multilingüe)**

```bash
uv run python -c "import whisper; model = whisper.load_model('small')"
```

Esto descarga el modelo (~244MB) a `~/.cache/whisper/`

---

## Task 2: Crear módulo de transcripción

**Files:**
- Create: `messaging/transcription.py`

**Step 1: Crear archivo con el transcribidor**

```python
"""
Voice transcription service using Whisper.

Uses memory storage for pending transcriptions to handle Telegram's 64-byte callback data limit.
"""

import os
import tempfile
import whisper
import uuid
import time
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Handle audio transcription using Whisper."""

    def __init__(self, model_name: str = "small", language: str = "es"):
        """
        Initialize transcription service.

        Args:
            model_name: Whisper model (tiny, base, small, medium, large)
            language: Language code ("es" for Spanish, None for auto-detect)
        """
        self.model_name = model_name
        self.language = language
        self.model = None
        # Memory storage for transcriptions (key: voice_id, value: dict with text and timestamp)
        self._pending_transcriptions: Dict[str, Dict] = {}

    async def load_model(self) -> None:
        """Load Whisper model lazily."""
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            logger.info(f"Whisper model loaded: {self.model_name}")

    def store_transcription(self, text: str, ttl_minutes: int = 15) -> str:
        """
        Store transcription in memory and return voice_id.

        Args:
            text: Transcribed text
            ttl_minutes: Time to live in minutes

        Returns:
            voice_id to reference this transcription
        """
        voice_id = str(uuid.uuid4())
        self._pending_transcriptions[voice_id] = {
            "text": text,
            "timestamp": time.time(),
            "ttl_minutes": ttl_minutes
        }
        self._cleanup_expired()
        return voice_id

    def get_transcription(self, voice_id: str) -> Optional[str]:
        """
        Retrieve transcription by voice_id.

        Args:
            voice_id: ID returned by store_transcription

        Returns:
            The transcribed text or None if not found/expired
        """
        self._cleanup_expired()
        data = self._pending_transcriptions.get(voice_id)
        if data:
            # Return text and remove from storage
            text = data["text"]
            del self._pending_transcriptions[voice_id]
            return text
        return None

    def _cleanup_expired(self) -> None:
        """Remove expired transcriptions from memory."""
        now = time.time()
        expired_keys = [
            key for key, data in self._pending_transcriptions.items()
            if now - data["timestamp"] > data["ttl_minutes"] * 60
        ]
        for key in expired_keys:
            del self._pending_transcriptions[key]

    async def transcribe_audio(
        self, audio_path: str, timeout: int = 60
    ) -> Tuple[str, Optional[float]]:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            timeout: Max seconds to wait

        Returns:
            Tuple of (transcription_text, confidence_score)

        Raises:
            Exception: If transcription fails
        """
        await self.load_model()

        logger.info(f"Transcribing audio: {audio_path}")

        # Transcribe
        result = self.model.transcribe(
            audio_path,
            language=self.language,
            verbose=False
        )

        text = result.get("text", "").strip()
        confidence = result.get("confidence")  # May be None

        logger.info(f"Transcription complete: {len(text)} chars")
        return text, confidence

    async def transcribe_ogg_data(self, ogg_data: bytes) -> Tuple[str, str]:
        """
        Transcribe OGG audio data directly and return (text, voice_id).

        Args:
            ogg_data: Raw OGG audio bytes from Telegram

        Returns:
            Tuple of (transcribed_text, voice_id)
        """
        # Save OGG to temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
            ogg_file.write(ogg_data)
            ogg_path = ogg_file.name

        try:
            # Convert to WAV (Whisper works better with WAV)
            wav_path = ogg_path.replace(".ogg", ".wav")

            # Use ffmpeg to convert
            import subprocess

            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i", ogg_path,
                    "-acodec", "pcm_s16le",
                    "-ar", "16000",
                    "-ac", "1",
                    wav_path
                ],
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                raise Exception(f"ffmpeg error: {result.stderr.decode()}")

            # Transcribe WAV
            text, _ = await self.transcribe_audio(wav_path)

            # Store transcription and return voice_id
            voice_id = self.store_transcription(text, ttl_minutes=15)

            return text, voice_id

        finally:
            # Cleanup
            if os.path.exists(ogg_path):
                os.unlink(ogg_path)
            if 'wav_path' in locals() and os.path.exists(wav_path):
                os.unlink(wav_path)


# Global singleton
transcription_service = TranscriptionService(model_name="small", language="es")
```

**Step 2: Crear test básico**

```python
# tests/test_transcription.py

import pytest
import asyncio
from messaging.transcription import TranscriptionService


@pytest.mark.asyncio
async def test_transcription_service_initialization():
    service = TranscriptionService()
    await service.load_model()
    assert service.model is not None
```

**Step 3: Correr test**

```bash
uv run pytest tests/test_transcription.py -v
```

Expected: FAIL (el modelo no está descargado aún, pero pasará después)

---

## Task 3: Agregar soporte para mensajes de voz en Telegram

**Files:**
- Modify: `messaging/telegram.py`

**Step 1: Importar transcription service**

```python
# Add after the telegram imports in telegram.py
try:
    from .transcription import transcription_service
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False
    transcription_service = None
```

**Step 2: Agregar handler para mensajes de voz**

En `__init__` después de los handlers existentes:

```python
# Register voice message handler
self._application.add_handler(
    MessageHandler(filters.VOICE, self._on_voice_message)
)
```

**Step 3: Implementar `_on_voice_message`**

```python
async def _on_voice_message(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle incoming voice messages."""
    if (
        not update.message
        or not update.message.voice
        or not update.effective_user
        or not update.effective_chat
    ):
        return

    if not TRANSCRIPTION_AVAILABLE:
        logger.error("Voice transcription not available")
        return

    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    # Security check
    if self.allowed_user_id:
        if user_id != str(self.allowed_user_id).strip():
            logger.warning(f"Unauthorized voice message from {user_id}")
            return

    # Download voice file
    voice_file = await update.message.voice.get_file()
    ogg_data = await voice_file.download_as_bytearray()

    # Send status message
    status_msg = await update.message.reply_text(
        "⏳ **Transcribiendo audio...**",
        parse_mode="markdown"
    )

    try:
        # Transcribe
        transcription = await transcription_service.transcribe_ogg_data(bytes(ogg_data))

        if not transcription or len(transcription.strip()) < 5:
            await status_msg.edit_text(
                "⚠️ **No se pudo transcribir el audio o está vacío**",
                parse_mode="markdown"
            )
            return

        # Show preview with confirmation buttons
        preview_text = f"**Transcripción:**\n```\n{transcription}\n```\n\n¿Enviar a Claude Code?"

        # Create keyboard with confirmation buttons
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [
                InlineKeyboardButton("✅ Enviar", callback_data=f"confirm_voice:{transcription}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_voice")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_msg.edit_text(
            preview_text,
            parse_mode="markdown",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        await status_msg.edit_text(
            f"❌ **Error en transcripción:** {str(e)[:200]}",
            parse_mode="markdown"
        )
```

**Step 4: Agregar handler para callbacks de botones**

```python
# Register callback handler for confirmation buttons
self._application.add_handler(
    CallbackQueryHandler(self._on_voice_confirmation)
)
```

**Step 5: Implementar `_on_voice_confirmation`**

```python
async def _on_voice_confirmation(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle voice message confirmation buttons."""
    if not update.callback_query or not update.effective_message:
        return

    query = update.callback_query
    await query.answer()

    if query.data.startswith("confirm_voice:"):
        # Extract voice_id (not the full transcription)
        voice_id = query.data.replace("confirm_voice:", "", 1)

        # Retrieve transcription from storage
        transcription = transcription_service.get_transcription(voice_id)

        if not transcription:
            await query.message.edit_text(
                "⚠️ **La transcripción expiró o no se encontró. Inténtalo de nuevo.",
                parse_mode="markdown"
            )
            return

        # Update message to show it's being sent
        await query.message.edit_text(
            "⏳ **Enviando a Claude Code...**",
            parse_mode="markdown"
        )

        # Create IncomingMessage with transcription text
        incoming = IncomingMessage(
            text=transcription,
            chat_id=str(update.effective_chat.id),
            user_id=str(update.effective_user.id),
            message_id=str(update.effective_message.message_id),
            platform="telegram",
            raw_event=update,
        )

        # Send to message handler
        if self._message_handler:
            try:
                await self._message_handler(incoming)
            except Exception as e:
                logger.error(f"Error handling voice transcription: {e}")
                await query.message.edit_text(
                    f"❌ **Error al enviar:** {str(e)[:200]}",
                    parse_mode="markdown"
                )

    elif query.data == "cancel_voice":
        await query.message.edit_text(
            "❌ **Cancelado**",
            parse_mode="markdown"
        )
```

**Step 6: Importar CallbackQueryHandler**

```python
# Add to imports
from telegram.ext import CallbackQueryHandler
```

**Step 7: Test manual básico**

```bash
# Run the server
uv run uvicorn server:app --host 0.0.0.0 --port 8082

# In another terminal, send a voice message to your Telegram bot
# You should see "Transcribiendo audio..." and then the preview
```

Expected behavior:
- Al enviar nota de voz: muestra "Transcribiendo audio..."
- Luego muestra preview con los botones ✅ y ❌
- Al presionar ✅: envía el texto a Claude Code

---

## Task 4: Agregar soporte para audio en IncomingMessage

**Files:**
- Modify: `messaging/models.py`

**Step 1: Agregar campos para audio a IncomingMessage**

```python
@dataclass
class IncomingMessage:
    text: str
    chat_id: str
    user_id: str
    message_id: str
    platform: str

    # Optional fields
    reply_to_message_id: Optional[str] = None
    username: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # NEW: Audio fields
    audio_data: Optional[bytes] = None  # Raw audio bytes
    audio_mime_type: Optional[str] = None  # e.g., "audio/ogg"

    # Platform-specific raw event
    raw_event: Any = None
```

**Step 2: Agregar método de fábrica para mensajes de voz**

```python
@staticmethod
def from_voice_message(
    text: str,
    chat_id: str,
    user_id: str,
    message_id: str,
    platform: str,
    audio_data: bytes,
    audio_mime_type: str,
    reply_to_message_id: Optional[str] = None
) -> "IncomingMessage":
    """Factory for voice messages."""
    return IncomingMessage(
        text=text,
        chat_id=chat_id,
        user_id=user_id,
        message_id=message_id,
        platform=platform,
        audio_data=audio_data,
        audio_mime_type=audio_mime_type,
        reply_to_message_id=reply_to_message_id
    )
```

---

## Task 5: Agregar límite de tamaño de audio

**Files:**
- Modify: `config/settings.py`

**Step 1: Agregar configuración de límite de audio**

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Voice message settings
    MAX_VOICE_MESSAGE_SIZE_MB: int = 10  # 10MB max
    VOICE_MESSAGE_TIMEOUT_SECONDS: int = 60
```

**Step 2: Usar el límite en telegram.py**

En `_on_voice_message`:

```python
# Check file size
if update.message.voice.file_size > (settings.MAX_VOICE_MESSAGE_SIZE_MB * 1024 * 1024):
    await update.message.reply_text(
        f"⚠️ **El archivo es demasiado grande**\n\nMáximo: {settings.MAX_VOICE_MESSAGE_SIZE_MB}MB",
        parse_mode="markdown"
    )
    return
```

**Step 3: Agregar configuración a .env.example**

```dotenv
# Voice transcription settings
MAX_VOICE_MESSAGE_SIZE_MB=10
VOICE_MESSAGE_TIMEOUT_SECONDS=60
WHISPER_MODEL=small
WHISPER_LANGUAGE=es
```

---

## Task 6: Tests y validación

**Step 1: Crear test de integración para transcripción**

```bash
# tests/test_integration_voice.py

import pytest
from messaging.transcription import TranscriptionService
import asyncio


@pytest.mark.asyncio
async def test_transcribe_sample_audio():
    """Test transcription with a sample audio file."""
    service = TranscriptionService()

    # Create a small test audio file (we can generate silence)
    import numpy as np
    import soundfile as sf
    import tempfile

    # Generate 1 second of "silence" audio
    duration = 1.0
    sample_rate = 16000
    audio_data = np.zeros(int(duration * sample_rate), dtype=np.float32)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio_data, sample_rate)
        wav_path = f.name

    try:
        text, confidence = await service.transcribe_audio(wav_path)
        # Should return empty or very short text for silence
        assert isinstance(text, str)
        assert confidence is None or isinstance(confidence, float)
    finally:
        import os
        os.unlink(wav_path)
```

**Step 2: Correr tests de integración**

```bash
uv run pytest tests/test_integration_voice.py -v
```

**Step 3: Test completo del flujo de Telegram**

```bash
# In one terminal
uv run uvicorn server:app --host 0.0.0.0 --port 8082 --reload

# In another terminal, monitor logs
tail -f agent_workspace/logs/*.log
```

Send test voice message to Telegram bot:
1. Enviar nota de voz corta (2-3 segundos)
2. Verificar que muestra "Transcribiendo audio..."
3. Verificar que muestra preview con texto
4. Presionar ✅ para enviar
5. Verificar que Claude Code recibe y procesa el texto

---

## Task 7: Mejoras y optimización

**Step 1: Agregar caché de modelo**

Modificar `TranscriptionService` para que el modelo se cargue solo una vez al iniciar:

```python
# In messaging/transcription.py

@asynccontextmanager
async def get_transcription_service():
    """Context manager for transcription service."""
    service = TranscriptionService()
    await service.load_model()
    yield service
```

**Step 2: Agregar rate limiting para transcripción**

En `messaging/limiter.py`:

```python
# Add transcription rate limiter
from aiolimiter import AsyncLimiter

transcription_limiter = AsyncLimiter(max_rate=1, time_period=5)  # 1 transcription per 5 seconds
```

**Step 3: Mejorar mensajes de error**

En `messaging/transcription.py`:

```python
class TranscriptionError(Exception):
    """Custom exception for transcription errors."""
    pass
```

**Step 4: Agregar estadísticas /stats**

Modificar `/stats` para incluir:
- Número de transcripciones realizadas
- Tiempo promedio de transcripción
- Idiomas detectados

---

## Task 8: Documentación

**Files:**
- Create: `docs/voice-messages.md`

**Step 1: Crear documentación de usuario**

```markdown
# Notas de Voz en Telegram

## Cómo usar

1. **Enviar nota de voz** - Simplemente envía una nota de voz al bot
2. **Esperar transcripción** - El bot mostrará "Transcribiendo audio..."
3. **Revisar preview** - Verás el texto transcrito con dos botones:
   - ✅ **Enviar** - Enviar el texto a Claude Code
   - ❌ **Cancelar** - Descartar la transcripción
4. **Confirmar** - Presiona ✅ para enviar el texto a Claude Code

## Límites

- Tamaño máximo: 10MB
- Duración máxima: 5 minutos
- Formato: OGG (formato nativo de Telegram)

## Idioma

Actualmente configurado para español. Para cambiar el idioma, modifica `WHISPER_LANGUAGE` en `.env`.

## Solución de problemas

### "No se pudo transcribir el audio"
- Asegúrate de que el audio es claro
- Intenta hablar más cerca del micrófono
- Verifica que el archivo no excede 10MB

### "Error en transcripción"
- Verifica que ffmpeg esté instalado: `ffmpeg -version`
- Revisa los logs: `cat agent_workspace/logs/*.log`
- Verifica que el modelo Whisper está descargado
```

**Step 2: Actualizar README.md**

Agregar sección:

```markdown
### Notas de Voz

Puedes enviar notas de voz por Telegram y se transcribirán automáticamente usando Whisper AI:

1. Enviar nota de voz al bot
2. Revisar el preview de la transcripción
3. Confirmar para enviar a Claude Code

Ver [docs/voice-messages.md](docs/voice-messages.md) para más detalles.
```

---

## Resumen de Archivos Modificados/Creados

**Nuevos archivos:**
- `messaging/transcription.py` - Servicio de transcripción
- `tests/test_transcription.py` - Tests unitarios
- `tests/test_integration_voice.py` - Tests de integración
- `docs/voice-messages.md` - Documentación de usuario

**Archivos modificados:**
- `messaging/telegram.py` - Handlers de voz y confirmación
- `messaging/models.py` - Agregar campos de audio
- `config/settings.py` - Agregar configuración de audio
- `pyproject.toml` - Agregar dependencias
- `.env.example` - Agregar variables de entorno

**Líneas de código estimadas:**
- ~300 líneas de implementación
- ~100 líneas de tests
- ~50 líneas de documentación

---

## Próximos Pasos

Después de implementar todo el plan, prueba:

1. **Prueba básica**: Envía una nota de voz corta (3-5 segundos)
2. **Prueba de límite**: Envía una nota de 15-20 segundos
3. **Prueba de cancelación**: Cancela el envío en el preview
4. **Prueba de error**: Envía audio con mucho ruido de fondo
5. **Prueba de integridad**: Verifica que Claude Code procesa el texto correctamente

Si todo funciona, ¡la funcionalidad está completa!
