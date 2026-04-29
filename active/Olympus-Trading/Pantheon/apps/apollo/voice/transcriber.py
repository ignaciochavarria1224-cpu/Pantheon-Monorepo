import tempfile
import os
from faster_whisper import WhisperModel
from core.audit import log

_model = None

def get_model():
    global _model
    if _model is None:
        print("Loading Whisper model (first time only)...")
        _model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _model

def transcribe_audio_file(audio_path: str) -> str:
    model = get_model()
    segments, _ = model.transcribe(audio_path, beam_size=5)
    text = " ".join([seg.text for seg in segments]).strip()
    log(f"Transcribed: '{text[:80]}'", system="VOICE")
    return text

def transcribe_bytes(audio_bytes: bytes, extension: str = "wav") -> str:
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        return transcribe_audio_file(tmp_path)
    finally:
        os.unlink(tmp_path)
