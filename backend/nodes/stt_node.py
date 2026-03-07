import io
import logging
import threading
import time

import numpy as np
from faster_whisper import WhisperModel

from nodes.base import Node, MessageBus, Message

log = logging.getLogger(__name__)

DEFAULT_MODEL = "base.en"
CHUNK_INTERVAL = 3.0  # seconds between partial transcriptions


class STTNode(Node):
    """Streams speech-to-text while listening, publishing partial results every
    few seconds and a final result when listening stops."""

    def __init__(
        self,
        bus: MessageBus,
        model_size: str = DEFAULT_MODEL,
        sample_rate: int = 16000,
        chunk_interval: float = CHUNK_INTERVAL,
    ):
        super().__init__("stt", bus)
        self.sample_rate = sample_rate
        self.chunk_interval = chunk_interval
        self._lock = threading.Lock()
        self._audio_buffer = io.BytesIO()
        self._listening = False
        self._last_transcribe_pos = 0

        log.info(f"[stt] loading whisper model '{model_size}' (cpu, int8)...")
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        log.info("[stt] model loaded")

        self.subscribe("serial/audio_in", self._on_audio_in)
        self.subscribe("state/listening", self._on_listening)

    # -- callbacks -----------------------------------------------------------

    def _on_audio_in(self, msg: Message):
        if self._listening:
            with self._lock:
                self._audio_buffer.write(msg.data)

    def _on_listening(self, msg: Message):
        listening: bool = msg.data
        if listening:
            with self._lock:
                self._audio_buffer = io.BytesIO()
                self._last_transcribe_pos = 0
            self._listening = True
            log.info("[stt] recording started")
        else:
            self._listening = False
            with self._lock:
                audio_data = self._audio_buffer.getvalue()
                self._audio_buffer = io.BytesIO()
                self._last_transcribe_pos = 0
            if audio_data:
                log.info(f"[stt] final transcription of {len(audio_data)} bytes")
                text = self._transcribe(audio_data)
                if text:
                    self.publish("stt/transcription", text)
            else:
                log.warning("[stt] no audio captured")

    def _transcribe(self, audio_data: bytes) -> str:
        """Convert raw PCM bytes to float32 numpy array and run whisper."""
        audio_np = (
            np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        )

        segments, info = self._model.transcribe(
            audio_np,
            beam_size=5,
            language="en",
            vad_filter=True,
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text

    def _run(self):
        """Periodically transcribe the full buffer while listening."""
        last_check = time.monotonic()
        while self._running:
            time.sleep(0.1)

            if not self._listening:
                last_check = time.monotonic()
                continue

            now = time.monotonic()
            if now - last_check < self.chunk_interval:
                continue
            last_check = now

            with self._lock:
                audio_data = self._audio_buffer.getvalue()
                buf_len = len(audio_data)

            if buf_len <= self._last_transcribe_pos:
                continue

            self._last_transcribe_pos = buf_len
            text = self._transcribe(audio_data)
            if text:
                log.info(f"[stt] partial: {text!r}")
                self.publish("stt/partial", text)
