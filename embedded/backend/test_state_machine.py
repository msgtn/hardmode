"""Interactive test: mock serial events via terminal input to drive the state machine.

Usage:
  uv run python test_state_machine.py                      # state machine only (no models)
  uv run python test_state_machine.py --serial              # include serial node
  uv run python test_state_machine.py --stt                 # include STT node
  uv run python test_state_machine.py --tts                 # include TTS node
  uv run python test_state_machine.py --api                  # include API node
  uv run python test_state_machine.py --serial --stt --tts --api  # include all
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
  bd / base_down        - send base button down
  bu / base_up          - send base button up
  o / open_lid          - send open_lid button press
  c / close_lid         - send close_lid button press
  a / audio [n]         - send n audio chunks (default 10)
  t / transcribe TEXT   - inject transcription result
  d / done              - send SPEECH_DONE event
  s / state             - print current state
  q / quit              - exit
  h / help              - show this help
""".strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--serial", action="store_true", help="Load serial node (reads from device)"
    )
    parser.add_argument(
        "--stt", action="store_true", help="Load STT node with whisper model"
    )
    parser.add_argument(
        "--tts", action="store_true", help="Load TTS node with piper model"
    )
    parser.add_argument(
        "--api", action="store_true", help="Load API node (HTTP server)"
    )
    args = parser.parse_args()

    bus = MessageBus()
    state_machine = StateMachineNode(bus)
    nodes = [state_machine]

    if args.serial:
        from nodes import SerialNode

        serial_node = SerialNode(bus)
        nodes.append(serial_node)
    else:
        log.info("[test] Serial node skipped (use --serial to enable)")

    if args.stt:
        from nodes import STTNode

        stt = STTNode(bus)
        nodes.append(stt)
    else:
        log.info("[test] STT node skipped (use --stt to enable)")

    if args.tts:
        from nodes import TTSNode

        tts = TTSNode(bus)
        nodes.append(tts)
    else:
        log.info("[test] TTS node skipped (use --tts to enable)")

    if args.api:
        from nodes import APINode

        api = APINode(bus)
        nodes.append(api)
    else:
        log.info("[test] API node skipped (use --api to enable)")

    def on_partial(msg):
        print(f"\r  [partial] {msg.data}", flush=True)

    def on_final(msg):
        print(f"\n  [final]   {msg.data}", flush=True)

    bus.subscribe("stt/partial", on_partial)
    bus.subscribe("stt/transcription", on_final)

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

        if cmd in ("bd", "base_down"):
            bus.publish(
                "serial/button", {"id": 0x01, "name": "base_down", "action": "down"}
            )

        elif cmd in ("bu", "base_up"):
            bus.publish(
                "serial/button", {"id": 0x01, "name": "base_up", "action": "up"}
            )

        elif cmd in ("o", "open_lid_up", "open", "lid"):
            bus.publish("serial/button", {"id": 0x02, "name": "open_lid_up"})

        elif cmd in ("c", "open_lid_down", "close"):
            bus.publish("serial/button", {"id": 0x02, "name": "open_lid_down"})

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
