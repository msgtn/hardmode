"""Mock test: drive the state machine and STT node without real serial hardware."""

import logging
import time

from nodes import MessageBus, StateMachineNode, STTNode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    bus = MessageBus()

    state_machine = StateMachineNode(bus)
    stt = STTNode(bus)

    state_machine.start()
    stt.start()

    time.sleep(0.2)

    # Simulate button press -> IDLE to LISTENING
    print("\n--- Button press (start listening) ---")
    bus.publish("serial/button", 1)
    time.sleep(0.2)

    # Simulate audio chunks arriving while listening
    print("\n--- Sending audio chunks ---")
    for i in range(5):
        bus.publish("serial/audio_in", b"\x00\x01" * 160)
        time.sleep(0.02)

    # Simulate button press -> LISTENING to PROCESSING
    print("\n--- Button press (stop listening) ---")
    bus.publish("serial/button", 1)
    time.sleep(0.2)

    # Simulate a transcription result (as if STT had a real engine)
    print("\n--- Injecting transcription ---")
    bus.publish("stt/transcription", "hello world")
    time.sleep(0.2)

    # Simulate speech done -> back to IDLE
    print("\n--- Speech done ---")
    from nodes.state_machine_node import Event
    state_machine._transition(Event.SPEECH_DONE)
    time.sleep(0.2)

    print(f"\nFinal state: {state_machine.state}")

    state_machine.stop()
    stt.stop()
    bus.close()


if __name__ == "__main__":
    main()
