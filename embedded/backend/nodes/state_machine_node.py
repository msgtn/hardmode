import time
import logging
import random
import uuid
from enum import Enum, auto

from nodes.base import Node, MessageBus, Message, Question

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = auto()
    IDLE_WAIT = auto()
    IDLE_ANSWER = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    SPEAKING_ACK = auto()
    SPEAKING_ANSWER = auto()


class Event(Enum):
    BUTTON_BASE_DOWN = auto()
    BUTTON_BASE_UP = auto()
    BUTTON_OPEN_LID = auto()
    BUTTON_CLOSE_LID = auto()
    TRANSCRIPTION_READY = auto()
    SPEECH_DONE = auto()


TRANSITIONS: dict[tuple[State, Event], State] = {
    # base button down: start listening
    (State.IDLE, Event.BUTTON_BASE_DOWN): State.LISTENING,
    (State.SPEAKING, Event.BUTTON_BASE_DOWN): State.LISTENING,
    (State.SPEAKING, Event.SPEECH_DONE): State.IDLE_WAIT,
    (State.IDLE_WAIT, Event.BUTTON_BASE_DOWN): State.LISTENING,
    # base button up while listening: stop listening, start processing
    (State.LISTENING, Event.BUTTON_BASE_UP): State.PROCESSING,
    # (State.LISTENING, Event.BUTTON_BASE_UP): State.SP,
    # base button up while processing: speak the transcription
    # (State.PROCESSING, Event.BUTTON_BASE_UP): State.SPEAKING,
    (State.LISTENING, Event.TRANSCRIPTION_READY): State.SPEAKING_ACK,
    (State.PROCESSING, Event.TRANSCRIPTION_READY): State.SPEAKING_ACK,
    # open lid: go straight to speaking a prompt
    (State.IDLE, Event.BUTTON_OPEN_LID): State.SPEAKING,
    # speech finishes
    (State.SPEAKING_ACK, Event.SPEECH_DONE): State.SPEAKING_ANSWER,
    (State.SPEAKING_ANSWER, Event.SPEECH_DONE): State.IDLE_ANSWER,
    (State.IDLE_ANSWER, Event.BUTTON_BASE_DOWN): State.SPEAKING_ANSWER,
    # (State.SPEAKING, Event.SPEECH_DONE): State.IDLE,
}

OPEN_LID_PROMPT = "What is the most embarrassing thing you've done?"


class StateMachineNode(Node):
    """Manages application state driven by serial and STT events."""

    def __init__(self, bus: MessageBus):
        super().__init__("state_machine", bus)
        self.state = State.IDLE

        self._random_question: Question | None = None
        self._session_id: str = ""
        self._answers: list[str] = []
        self._similar_answer: str | None = None
        self._first_answer_spoken: bool = False

        self.subscribe("serial/button", self._on_button)
        self.subscribe("stt/transcription", self._on_transcription)
        self.subscribe("stt/partial", self._on_transcription)
        self.subscribe("tts/done", self._on_tts_done)
        self.subscribe("api/questions/random/response", self._on_random_question)
        self.subscribe("api/answers/response", self._on_answers)
        self.subscribe("api/similar/response", self._on_similar)

    def _fetch_random_question(self):
        self._session_id = str(uuid.uuid4())
        self._first_answer_spoken = False
        self._similar_answer = None
        log.info(f"[state_machine] new session_id={self._session_id}")
        self.publish("api/questions/random", {})

    def _transition(self, event: Event):
        if event == Event.BUTTON_CLOSE_LID:
            prev = self.state
            self.state = State.IDLE
            log.info(f"[state_machine] {prev.name} -> IDLE (on BUTTON_CLOSE_LID)")
            self.publish(
                "state/changed", {"from": prev, "to": State.IDLE, "event": event}
            )
            if prev == State.LISTENING:
                self.publish("state/listening", False)
                self.publish("serial/led", {"led": "red", "on": False})
            if prev in (State.SPEAKING, State.SPEAKING_ACK, State.SPEAKING_ANSWER):
                self.publish("serial/led", {"led": "green", "on": False})
            self._fetch_random_question()
            return

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

        SPEAKING_STATES = (State.SPEAKING, State.SPEAKING_ACK, State.SPEAKING_ANSWER)
        if next_state in SPEAKING_STATES and prev not in SPEAKING_STATES:
            self.publish("serial/led", {"led": "green", "on": True})
        elif prev in SPEAKING_STATES and next_state not in SPEAKING_STATES:
            self.publish("serial/led", {"led": "green", "on": False})

        if next_state == State.SPEAKING_ACK:
            log.info("[state_machine] requesting TTS: 'thanks!'")
            self.publish("tts/speak", "thanks!")
            if self._random_question:
                self.publish(
                    "api/submit",
                    {
                        "question_id": self._random_question.id,
                        "answer": getattr(self, "_last_transcription", ""),
                        "uuid": self._session_id,
                    },
                )

        if next_state == State.SPEAKING_ANSWER:
            if not self._first_answer_spoken:
                self.publish("tts/speak", "Looking for similar answers...")
                time.sleep(2)
                if self._random_question:
                    self.publish(
                        "api/similar",
                        {
                            "question_id": self._random_question.id,
                            "uuid": self._session_id,
                        },
                    )
                for _ in range(12):
                    if self._similar_answer:
                        break
                    time.sleep(0.2)

                self._first_answer_spoken = True
                if self._similar_answer:
                    text = "A similar answer: " + self._similar_answer
                else:
                    text = "Someone else's answer: " + random.choice(self._answers)
            else:
                if self._answers:
                    text = "Someone else's answer: " + random.choice(self._answers)
                else:
                    text = "There are no other answers for this question."
            log.info(f"[state_machine] requesting TTS (answer): {text!r}")
            self.publish("tts/speak", text)

        if next_state == State.IDLE:
            self._fetch_random_question()

        if next_state == State.SPEAKING:
            text = (
                self._random_question.text if self._random_question else OPEN_LID_PROMPT
            )
            log.info(f"[state_machine] requesting TTS: {text!r}")
            self.publish("tts/speak", text)

    # -- callbacks -----------------------------------------------------------

    def _on_button(self, msg: Message):
        button = msg.data
        name = button["name"]
        log.info(
            f"[state_machine] button event received: {name} (state={self.state.name})"
        )

        if name == "open_lid_up":
            self._transition(Event.BUTTON_OPEN_LID)
        elif name == "open_lid_down":
            self._transition(Event.BUTTON_CLOSE_LID)
        elif name == "base_down":
            if self.state == State.LISTENING:
                return
            self._transition(Event.BUTTON_BASE_DOWN)
        elif name == "base_up":
            self._transition(Event.BUTTON_BASE_UP)
        else:
            log.warning(f"[state_machine] unknown button type: {name}")

    def _on_random_question(self, msg: Message):
        question: Question = msg.data
        self._random_question = question
        log.info(
            f"[state_machine] stored random question (id={question.id}): {question.text!r}"
        )
        self.publish("api/answers", {"question_id": question.id})

    def _on_similar(self, msg: Message):
        self._similar_answer = msg.data
        log.info(f"[state_machine] similar answer: {msg.data!r}")

    def _on_answers(self, msg: Message):
        self._answers = msg.data
        log.info(f"[state_machine] cached {len(self._answers)} answers")

    def _on_transcription(self, msg: Message):
        text = msg.data
        log.info(f"[state_machine] transcription: {text!r}")
        self._last_transcription = text
        self.publish("state/transcription_text", text)
        self._transition(Event.TRANSCRIPTION_READY)

    def _on_tts_done(self, msg: Message):
        log.info("[state_machine] TTS playback finished")
        self._transition(Event.SPEECH_DONE)

    def _run(self):
        import time

        self._fetch_random_question()

        while self._running:
            time.sleep(0.1)
