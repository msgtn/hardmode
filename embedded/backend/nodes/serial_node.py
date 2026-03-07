import logging
import struct
import time

import serial

from nodes.base import Node, MessageBus, Message

log = logging.getLogger(__name__)

# Protocol: each frame from the device is:
#   [1 byte type] [2 bytes length (big-endian)] [length bytes payload]
# Types:
FRAME_AUDIO = 0x01
FRAME_BUTTON = 0x02

# Outbound frame types (to device):
FRAME_AUDIO_OUT = 0x81
FRAME_LED = 0x82

# Button IDs (first byte of FRAME_BUTTON payload)
BUTTON_BASE = 0x01
BUTTON_OPEN_LID = 0x02

# Action byte (second byte of FRAME_BUTTON payload)
ACTION_UP = 0x00
ACTION_DOWN = 0x01

BUTTON_NAMES = {
    BUTTON_BASE: "base",
    BUTTON_OPEN_LID: "open_lid",
}


class SerialNode(Node):
    """Reads/writes serial frames. Publishes audio_in and button topics,
    subscribes to audio_out and led to send data to the device."""

    def __init__(
        self,
        bus: MessageBus,
        port: str = "/dev/ttyACM0",
        baudrate: int = 115_200,
        timeout: float = 0.01,
    ):
        super().__init__("serial", bus)
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: serial.Serial | None = None

        self.subscribe("serial/audio_out", self._on_audio_out)
        self.subscribe("serial/led", self._on_led)
        self.subscribe("serial/trigger_button", self._on_trigger_button)

    # -- callbacks -----------------------------------------------------------

    def _on_audio_out(self, msg: Message):
        """Send audio bytes to device, paced to match 16kHz playback."""
        data: bytes = msg.data
        max_payload = 1024  # 512 samples = 32ms at 16kHz
        for i in range(0, len(data), max_payload):
            self._send_frame(FRAME_AUDIO_OUT, data[i:i + max_payload])
            time.sleep(0.025)  # slightly under 32ms to keep buffer fed

    def _on_trigger_button(self, msg: Message):
        """Emit a button event from software. msg.data = {"name": "base_down"|"base_up"|"open_lid"}"""
        name = msg.data.get("name", "base_down")
        log.info(f"[serial] trigger button: {name}")
        # Parse action suffix if present
        action_name = "down"
        base_name = name
        for suffix in ("_down", "_up"):
            if name.endswith(suffix):
                base_name = name[: -len(suffix)]
                action_name = suffix[1:]
                break
        name_to_id = {v: k for k, v in BUTTON_NAMES.items()}
        button_id = name_to_id.get(base_name, BUTTON_BASE)
        self.publish("serial/button", {"id": button_id, "name": name, "action": action_name})

    def _on_led(self, msg: Message):
        """Send LED state to device. msg.data = {"led": str, "on": bool}"""
        led: str = msg.data["led"]
        on: bool = msg.data["on"]
        led_ids = {"red": 0, "green": 1, "blue": 2}
        led_id = led_ids.get(led, 0)
        payload = bytes([led_id, int(on)])
        log.info(f"[serial] LED {led} {'on' if on else 'off'}")
        self._send_frame(FRAME_LED, payload)

    # -- serial helpers ------------------------------------------------------

    def _open(self):
        while self._running:
            try:
                self._serial = serial.Serial(
                    self.port, self.baudrate, timeout=self.timeout
                )
                log.info(f"[serial] opened {self.port}")
                return
            except serial.SerialException:
                log.warning(f"[serial] waiting for {self.port}...")
                time.sleep(1)

    def _read_frame(self) -> tuple[int, bytes] | None:
        """Read one frame. Returns (type, payload) or None on timeout."""
        ser = self._serial
        if ser is None or not ser.is_open:
            return None

        header = ser.read(3)
        if len(header) < 3:
            return None

        frame_type = header[0]
        length = struct.unpack(">H", header[1:3])[0]
        payload = ser.read(length)
        if len(payload) < length:
            log.warning("[serial] truncated frame")
            return None

        return frame_type, payload

    def _send_frame(self, frame_type: int, payload: bytes):
        ser = self._serial
        if ser is None or not ser.is_open:
            return
        header = struct.pack(">BH", frame_type, len(payload))
        ser.write(header + payload)

    # -- main loop -----------------------------------------------------------

    def _run(self):
        self._open()
        while self._running:
            frame = self._read_frame()
            if frame is None:
                continue

            frame_type, payload = frame
            if frame_type == FRAME_AUDIO:
                self.publish("serial/audio_in", payload)
            elif frame_type == FRAME_BUTTON:
                button_id = payload[0] if payload else BUTTON_BASE
                action = payload[1] if len(payload) >= 2 else ACTION_DOWN
                button_name = BUTTON_NAMES.get(button_id, f"unknown_{button_id}")
                action_name = "down" if action == ACTION_DOWN else "up"
                name = f"{button_name}_{action_name}"
                log.info(f"[serial] button frame: id=0x{button_id:02x} ({name})")
                self.publish("serial/button", {"id": button_id, "name": name, "action": action_name})
            else:
                log.debug(f"[serial] unknown frame type 0x{frame_type:02x}")

        if self._serial and self._serial.is_open:
            self._serial.close()
