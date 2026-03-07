import logging
import time
from pathlib import Path

import numpy as np
from piper import PiperVoice

from nodes.base import Node, MessageBus, Message

log = logging.getLogger(__name__)

DEFAULT_MODEL = Path(__file__).parent.parent / "models" / "en_US-lessac-medium.onnx"


class TTSNode(Node):
    """Text-to-speech node using Piper. Converts text to PCM int16 audio
    and sends it to the serial node, then signals completion."""

    def __init__(self, bus: MessageBus, model_path: str | Path = DEFAULT_MODEL):
        super().__init__("tts", bus)

        log.info(f"[tts] loading piper model '{Path(model_path).name}'...")
        self._voice = PiperVoice.load(str(model_path))
        log.info(f"[tts] model loaded (sample_rate={self._voice.config.sample_rate})")

        self.subscribe("tts/speak", self._on_speak)

    def _on_speak(self, msg: Message):
        text: str = msg.data
        log.info(f"[tts] synthesizing: {text!r}")

        audio_chunks = []
        for chunk in self._voice.synthesize(text):
            pcm_bytes = chunk.audio_int16_bytes
            audio_chunks.append(pcm_bytes)
            self.publish("serial/audio_out", pcm_bytes)

        total_bytes = sum(len(c) for c in audio_chunks)
        log.info(f"[tts] sent {total_bytes} bytes of audio ({len(audio_chunks)} chunks)")
        self.publish("tts/done", True)

    def _run(self):
        while self._running:
            time.sleep(0.1)
