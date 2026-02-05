#!/usr/bin/env python3
"""
Test script to verify Whisper model loading with PyTorch 2.10.0
"""
import sys
sys.path.insert(0, '/home/vhpm18/Documentos/Ai/cc-nim')

from services.transcription import TranscriptionService

print("🧪 Testing Whisper model loading...")
print("=" * 60)

try:
    # Create service (lazy loading)
    service = TranscriptionService(model="small", device="auto")
    print(f"✅ TranscriptionService created (Device: {service.device}, Compute: {service.compute_type})")

    # Trigger model loading
    print("\n📥 Loading model (this will download if needed)...")
    model = service.model
    print("✅ Faster Whisper model loaded successfully!")

    print("\n" + "=" * 60)
    print("🎉 SUCCESS: faster-whisper is ready to transcribe!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
