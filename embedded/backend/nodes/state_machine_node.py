import logging
from enum import Enum, auto

from nodes.base import Node, MessageBus, Message

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()


class Event(Enum):
    BUTTON_BASE = auto()
    BUTTON_OPEN_LID = auto()
    TRANSCRIPTION_READY = auto()
    SPEECH_DONE = auto()


TRANSITIONS: dict[tuple[State, Event], State] = {
    # base button: toggle listening / stop listening
    (State.IDLE, Event.BUTTON_BASE): State.LISTENING,
    (State.LISTENING, Event.BUTTON_BASE): State.PROCESSING,
    # open lid: go straight to speaking a prompt
    (State.IDLE, Event.BUTTON_OPEN_LID): State.SPEAKING,
    # transcription finishes -> speak it back via TTS
    (State.PROCESSING, Event.TRANSCRIPTION_READY): State.SPEAKING,
    # speech finishes
    (State.SPEAKING, Event.SPEECH_DONE): State.IDLE,
}

OPEN_LID_PROMPT = "What is the most embarrassing thing you've done?"


class StateMachineNode(Node):
    """Manages application state driven by serial and STT events."""

    def __init__(self, bus: MessageBus):
        super().__init__("state_machine", bus)
        self.state = State.IDLE

        self.subscribe("serial/button", self._on_button)
        self.subscribe("stt/transcription", self._on_transcription)
        self.subscribe("tts/done", self._on_tts_done)

    def _transition(self, event: Event):
        key = (self.state, event)
        next_state = TRANSITIONS.get(key)
        if next_state is None:
            log.warning(f"[state_machine] no transition for {self.state} + {event}")
            return
        prev = self.state
        self.state = next_state
        log.info(f"[state_machine] {prev.name} -> {next_state.name} (on {event.name})")
        self.publish("state/changed", {"from": prev, "to": next_state, "event": event})

        # Side effects
        if next_state == State.LISTENING:
            self.publish("state/listening", True)
            self.publish("serial/led", {"led": "red", "on": True})
        elif prev == State.LISTENING:
            self.publish("state/listening", False)
            self.publish("serial/led", {"led": "red", "on": False})

        if next_state == State.SPEAKING:
            text = getattr(self, "_last_transcription", "") if prev == State.PROCESSING else OPEN_LID_PROMPT
            log.info(f"[state_machine] requesting TTS: {text!r}")
            self.publish("tts/speak", text)

    # -- callbacks -----------------------------------------------------------

    def _on_button(self, msg: Message):
        button = msg.data
        name = button["name"]
        log.info(f"[state_machine] button event received: {name} (state={self.state.name})")

        if name == "open_lid":
            self._transition(Event.BUTTON_OPEN_LID)
        elif name == "base":
            self._transition(Event.BUTTON_BASE)
        else:
            log.warning(f"[state_machine] unknown button type: {name}")

    def _on_transcription(self, msg: Message):
        text = msg.data
        log.info(f"[state_machine] transcription: {text!r}")
        self._last_transcription = text
        self._transition(Event.TRANSCRIPTION_READY)
        self.publish("state/transcription_text", text)

    def _on_tts_done(self, msg: Message):
        log.info("[state_machine] TTS playback finished")
        self._transition(Event.SPEECH_DONE)

    def _run(self):
        import time

        while self._running:
            time.sleep(0.1)
