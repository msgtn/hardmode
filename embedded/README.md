# Embedded Firmware

XIAO ESP32S3 Sense firmware that communicates with the backend over serial using a framed protocol. Reads audio from the built-in PDM microphone (16kHz, 16-bit mono) and sends it to the host.

## Prerequisites

- [Arduino CLI](https://arduino.github.io/arduino-cli/) or Arduino IDE
- ESP32 board package:
  ```bash
  arduino-cli config add board_manager.additional_urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
  arduino-cli core install esp32:esp32
  ```

## Compile and Upload

```bash
arduino-cli compile -b esp32:esp32:XIAO_ESP32S3 firmware/
arduino-cli upload -b esp32:esp32:XIAO_ESP32S3 -p /dev/ttyACM0 firmware/
```

## Protocol

Each serial frame is `[1 byte type] [2 bytes length (big-endian)] [length bytes payload]`.

| Type   | Direction     | Description          |
|--------|---------------|----------------------|
| `0x01` | Device → Host | Audio data           |
| `0x02` | Device → Host | Button press         |
| `0x81` | Host → Device | Audio out             |
| `0x82` | Host → Device | LED control          |

### Audio In (`0x01`)

Payload: 1024 bytes of raw 16-bit signed PCM (512 samples at 16kHz mono).

Captured from the built-in PDM microphone (GPIO42=CLK, GPIO41=DATA) and streamed continuously (~every 32ms).

### LED Control (`0x82`)

Payload: `[led_id, on/off]`

- `led_id` — ignored (only built-in LED on GPIO21)
- `on/off` — `1` = on, `0` = off (LED is active-low)

Triggered from the backend by publishing to `serial/led`, e.g. `{"led": "red", "on": true}`.

### Audio Out (`0x81`)

Payload: raw 16-bit signed PCM bytes (16kHz mono), any length.

Samples are queued into an 8192-sample ring buffer (~0.5s) and played back via PWM on **GPIO2** (D1/A1) using a 40kHz carrier with 8-bit resolution. A hardware timer ISR clocks out samples at ~16kHz.

**Wiring:** connect a speaker or amplifier to GPIO2 and GND. An RC low-pass filter (1kΩ + 100nF) between GPIO2 and the load will smooth the PWM into a cleaner analog signal.
