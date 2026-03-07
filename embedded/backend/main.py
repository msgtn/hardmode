import logging
import signal
import sys

from nodes import MessageBus, SerialNode, StateMachineNode, STTNode, TTSNode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main():
    bus = MessageBus()

    serial_node = SerialNode(bus, port="/dev/ttyACM0")
    state_machine = StateMachineNode(bus)
    stt = STTNode(bus)
    tts = TTSNode(bus)

    nodes = [serial_node, state_machine, stt, tts]

    for node in nodes:
        node.start()

    log.info("All nodes started. Press Ctrl+C to stop.")

    def shutdown(*_):
        log.info("Shutting down...")
        for node in nodes:
            node.stop()
        bus.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    signal.pause()


if __name__ == "__main__":
    main()
