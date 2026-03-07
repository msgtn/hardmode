import io
import logging
import time

import numpy as np
from faster_whisper import WhisperModel

from nodes.base import Node, MessageBus, Message

log = logging.getLogger(__name__)

DEFAULT_MODEL = "base.en"


class STTNode(Node):
    """Buffers audio while listening, then runs speech-to-text via faster-whisper on CPU."""

    def __init__(
        self,
        bus: MessageBus,
        model_size: str = DEFAULT_MODEL,
        sample_rate: int = 16000,
        sample_width: int = 1,
    ):
        super().__init__("stt", bus)
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self._audio_buffer = io.BytesIO()
        self._listening = False

        log.info(f"[stt] loading whisper model '{model_size}' (cpu, int8)...")
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        log.info("[stt] model loaded")

        self.subscribe("serial/audio_in", self._on_audio_in)
        self.subscribe("state/listening", self._on_listening)

    # -- callbacks -----------------------------------------------------------

    def _on_audio_in(self, msg: Message):
        if self._listening:
            self._audio_buffer.write(msg.data)

    def _on_listening(self, msg: Message):
        listening: bool = msg.data
        if listening:
            self._audio_buffer = io.BytesIO()
            self._listening = True
            log.info("[stt] recording started")
        else:
            self._listening = False
            audio_data = self._audio_buffer.getvalue()
            self._audio_buffer = io.BytesIO()
            if audio_data:
                log.info(f"[stt] processing {len(audio_data)} bytes of audio")
                self._transcribe(audio_data)
            else:
                log.warning("[stt] no audio captured")

    def _transcribe(self, audio_data: bytes):
        """Convert raw PCM bytes to float32 numpy array and run whisper."""
        # Raw PCM int16 -> float32 normalized to [-1, 1]
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

        if text:
            log.info(f"[stt] result: {text!r}")
            self.publish("stt/transcription", text)
        else:
            log.info("[stt] no speech detected")

    def _run(self):
        while self._running:
            time.sleep(0.1)
