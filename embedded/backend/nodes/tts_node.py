import logging
import time
from pathlib import Path

import numpy as np
from piper import PiperVoice

from nodes.base import Node, MessageBus, Message

log = logging.getLogger(__name__)

DEFAULT_MODEL = Path(__file__).parent.parent / "models" / "en_US-lessac-medium.onnx"
TARGET_SAMPLE_RATE = 16000


class TTSNode(Node):
    """Text-to-speech node using Piper. Converts text to PCM int16 audio,
    resamples to 16kHz for the microcontroller, and sends it to the serial node."""

    def __init__(self, bus: MessageBus, model_path: str | Path = DEFAULT_MODEL):
        super().__init__("tts", bus)

        log.info(f"[tts] loading piper model '{Path(model_path).name}'...")
        self._voice = PiperVoice.load(str(model_path))
        self._src_rate = self._voice.config.sample_rate
        log.info(f"[tts] model loaded (sample_rate={self._src_rate})")

        self._ratio = TARGET_SAMPLE_RATE / self._src_rate if self._src_rate != TARGET_SAMPLE_RATE else 0
        if self._ratio:
            log.info(f"[tts] will resample {self._src_rate}Hz -> {TARGET_SAMPLE_RATE}Hz")

        self.subscribe("tts/speak", self._on_speak)

    def _resample(self, pcm_bytes: bytes) -> bytes:
        """Resample int16 PCM from model sample rate to 16kHz using linear interpolation."""
        if not self._ratio:
            return pcm_bytes
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        out_len = int(len(samples) * self._ratio)
        x_old = np.arange(len(samples))
        x_new = np.linspace(0, len(samples) - 1, out_len)
        resampled = np.interp(x_new, x_old, samples)
        return np.clip(resampled, -32768, 32767).astype(np.int16).tobytes()

    def _on_speak(self, msg: Message):
        text: str = msg.data
        log.info(f"[tts] synthesizing: {text!r}")

        total_bytes = 0
        chunk_count = 0
        for chunk in self._voice.synthesize(text):
            pcm_bytes = self._resample(chunk.audio_int16_bytes)
            chunk_count += 1
            total_bytes += len(pcm_bytes)
            samples = len(pcm_bytes) // 2
            duration_ms = samples * 1000 // TARGET_SAMPLE_RATE
            log.info(f"[tts] chunk {chunk_count}: {len(pcm_bytes)} bytes, {samples} samples, ~{duration_ms}ms (int16 PCM {TARGET_SAMPLE_RATE}Hz)")
            self.publish("serial/audio_out", pcm_bytes)

        log.info(f"[tts] done: {total_bytes} bytes total ({chunk_count} chunks)")
        self.publish("tts/done", True)

    def _run(self):
        while self._running:
            time.sleep(0.1)
