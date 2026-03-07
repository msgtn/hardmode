# Embedded Firmware

Arduino Nano 33 IoT firmware that communicates with the backend over serial using a framed protocol.

## Prerequisites

- [Arduino CLI](https://arduino.github.io/arduino-cli/) or Arduino IDE
- Arduino SAMD Boards package:
  ```bash
  arduino-cli core install arduino:samd
  ```

## Compile and Upload

```bash
arduino-cli compile -b arduino:samd:nano_33_iot firmware/
arduino-cli upload -b arduino:samd:nano_33_iot -p /dev/ttyACM0 firmware/
```

## Protocol

Each serial frame is `[1 byte type] [2 bytes length (big-endian)] [length bytes payload]`.

| Type   | Direction     | Description          |
|--------|---------------|----------------------|
| `0x01` | Device → Host | Audio data           |
| `0x02` | Device → Host | Button press         |
| `0x81` | Host → Device | Audio out             |
| `0x82` | Host → Device | LED control          |

### LED Control (`0x82`)

Payload: `[led_id, on/off]`

- `led_id` — ignored (only built-in LED on pin 13)
- `on/off` — `1` = on, `0` = off

Triggered from the backend by publishing to `serial/led`, e.g. `{"led": "red", "on": true}`.
