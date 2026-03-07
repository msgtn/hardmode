"""Interactive test: mock serial events via terminal input to drive the state machine.

Usage:
  uv run python test_state_machine.py          # state machine only (no model load)
  uv run python test_state_machine.py --stt    # include STT node with whisper model
"""

import argparse
import logging
import signal
import sys

from nodes import MessageBus, StateMachineNode
from nodes.state_machine_node import Event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)-24s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

HELP = """
Commands:
  b / button [id]     - send button press (default id=1)
  a / audio [chunks]  - send audio chunks (default 10)
  t / transcribe TEXT  - inject transcription result
  d / done            - send SPEECH_DONE event
  s / state           - print current state
  q / quit            - exit
  h / help            - show this help
""".strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stt", action="store_true", help="Load STT node with whisper model")
    args = parser.parse_args()

    bus = MessageBus()
    state_machine = StateMachineNode(bus)
    nodes = [state_machine]

    if args.stt:
        from nodes import STTNode
        stt = STTNode(bus)
        nodes.append(stt)
    else:
        log.info("[test] STT node skipped (use --stt to enable)")

    for node in nodes:
        node.start()

    def shutdown(*_):
        print()
        for node in nodes:
            node.stop()
        bus.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    print(HELP)
    print(f"\nCurrent state: {state_machine.state.name}\n")

    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            shutdown()
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("b", "button"):
            button_id = int(arg) if arg.isdigit() else 1
            bus.publish("serial/button", button_id)

        elif cmd in ("a", "audio"):
            n = int(arg) if arg.isdigit() else 10
            for _ in range(n):
                bus.publish("serial/audio_in", b"\x00\x80" * 160)
            log.info(f"[test] sent {n} audio chunks")

        elif cmd in ("t", "transcribe"):
            text = arg or "hello world"
            bus.publish("stt/transcription", text)

        elif cmd in ("d", "done"):
            state_machine._transition(Event.SPEECH_DONE)

        elif cmd in ("s", "state"):
            print(f"State: {state_machine.state.name}")

        elif cmd in ("q", "quit"):
            shutdown()

        elif cmd in ("h", "help"):
            print(HELP)

        else:
            print(f"Unknown command: {cmd!r} (type 'h' for help)")


if __name__ == "__main__":
    main()
