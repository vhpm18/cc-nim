# Notas de Voz - Guía de Usuario

## ¿Cómo funciona?

Puedes enviar **notas de voz** a través de Telegram y el bot las transcribirá automáticamente usando **Whisper AI** (modelo pequeño en español).

### Flujo de trabajo:

1. ** Enviar nota de voz ** al bot de Telegram
2. ** Esperar transcripción ** - El bot muestra "⏳ Transcribiendo audio..."
3. ** Revisar preview ** - Verás el texto transcrito con dos botones:
   - ✅ ** Enviar ** - Enviar el texto a Claude Code
   - ❌ ** Cancelar ** - Descartar la transcripción
4. ** Confirmar ** - Presiona ✅ para enviar el texto a Claude Code

---

## Límites

- ** Tamaño máximo **: 10MB por nota de voz
- ** Duración máxima **: Aproximadamente 5-10 minutos (depende de la calidad)
- ** Formato **: OGG (formato nativo de Telegram)
- ** Tiempo de procesamiento **: 5-10 segundos para notas de 3-5 segundos

---

## Idioma

Actualmente configurado para ** español **. Para cambiar el idioma, modifica `WHISPER_LANGUAGE` en el archivo `.env`:

```dotenv
WHISPER_LANGUAGE=es  # Opciones: es, en, fr, de, etc.
```

---

## Solución de problemas

### "No se pudo transcribir el audio o está vacío"
- Asegúrate de que el audio sea claro, sin mucho ruido de fondo
- Habla más cerca del micrófono
- Evita notas de voz muy cortas (menos de 2 segundos)

### "Error en transcripción"
- Verifica que ffmpeg está instalado: `ffmpeg -version`
- Revisa los logs: `tail -f agent_workspace/logs/*.log`
- Verifica que el modelo Whisper está descargado: `ls -lh ~/.cache/whisper/small.pt`

### "El archivo es demasiado grande"
- Reduce la duración de la nota de voz
- El límite es 10MB (aprox 5-10 minutos)

### Transcripción captura logs en lugar de voz
- Esto indica problema de captura de audio
- Verificar configuración del bot de Telegram
- Asegurar que no hay múltiples instancias del servidor

---

## Ejemplos de uso

### Ejemplo 1: Tarea simple
** Audio: ** "Analiza el archivo README.md y dime qué hace este proyecto"

** Resultado esperado **: Claude lee el README y te explica el proyecto

### Ejemplo 2: Código
** Audio: ** "Crea una función que calcule el factorial de un número"

** Resultado esperado **: Claude genera código Python con la función factorial

### Ejemplo 3: Pregunta
** Audio: ** "¿Cuál es la capital de Francia?"

** Resultado esperado **: Claude responde "París"

---

## Configuración avanzada

### Variables de entorno (`.env`):

```dotenv
# Modelo Whisper (tiny, base, small, medium, large)
WHISPER_MODEL=small

# Idioma para transcripción
WHISPER_LANGUAGE=es

# Límite de tamaño de archivo (MB)
MAX_VOICE_MESSAGE_SIZE_MB=10

# Timeout para transcripción (segundos)
VOICE_MESSAGE_TIMEOUT_SECONDS=60
```

### Modelos disponibles

- ** tiny ** (39MB) - Inglés solo, rápido pero menos preciso
- ** base ** (74MB) - Inglés solo, balanceado
- ** small ** (244MB) - Multilingüe, buen balance (recomendado)
- ** medium ** (769MB) - Multilingüe, muy preciso
- ** large** (1.5GB) - Multilingüe, máxima precisión

**Recomendación para español**: `small` o `medium`

---

## Notas técnicas

### Arquitectura interna

1. ** Descarga **: Telegram envía OGG (Opus codec)
2. ** Conversión **: ffmpeg convierte OGG → WAV
3. ** Transcripción **: Whisper procesa WAV → texto
4. ** Preview** : Se muestra el texto con botones para confirmar
5. ** Envío **: Al confirmar, el texto se envía a Claude Code

### Requisitos del sistema

- **ffmpeg**: instalado y disponible en PATH
- **OpenAI Whisper**: modelo descargado (~244MB para 'small')
- **Python 3.10+** con dependencias de audio

### Almacenamiento de transcripciones

Las transcripciones se almacenan temporalmente:
- **Lugar** : Memoria RAM (dict)
- **TTL **: 15 minutos
- ** Limpieza **: Automática tras expiración

---

## Prueba rápida

** Envía una nota de voz corta así: **
1. Abre Telegram
2. Busca tu bot
3. Mantén presionado el micrófono
4. Di claramente: "Hola Claude, salúdame"
5. Suelta y envía
6. ** Deberías ver: ** transcripción → botones → respuesta de Claude

---

## Contribución

Para reportar bugs o sugerir mejoras:
- Abre un issue en el repositorio
- Incluye: tu audio de prueba (si aplica), logs, configuración `.env`

---

** Última actualización **: feb 2025
** Versión **: 2.0.0
