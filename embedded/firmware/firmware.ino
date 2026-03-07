#include <stdint.h>

// Frame types (must match backend/nodes/serial_node.py)
constexpr uint8_t FRAME_AUDIO     = 0x01;
constexpr uint8_t FRAME_BUTTON    = 0x02;
constexpr uint8_t FRAME_AUDIO_OUT = 0x81;
constexpr uint8_t FRAME_LED       = 0x82;

constexpr int LED_PIN = 13;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
}

void loop() {
  if (Serial.available() < 3) return;

  uint8_t frameType = Serial.read();
  uint8_t lenHi     = Serial.read();
  uint8_t lenLo     = Serial.read();
  uint16_t length   = (uint16_t(lenHi) << 8) | lenLo;

  // Read payload
  uint8_t payload[256];
  uint16_t toRead = min(length, (uint16_t)sizeof(payload));
  uint16_t got = 0;
  unsigned long start = millis();
  while (got < toRead && (millis() - start) < 100) {
    if (Serial.available()) {
      payload[got++] = Serial.read();
    }
  }
  // Discard any extra bytes beyond buffer
  for (uint16_t i = got; i < length; i++) {
    while (!Serial.available() && (millis() - start) < 100) {}
    if (Serial.available()) Serial.read();
  }

  if (got < toRead) return; // incomplete frame, discard

  if (frameType == FRAME_LED && got >= 2) {
    // payload[0] = led_id (ignored — we only have pin 13)
    // payload[1] = on/off
    digitalWrite(LED_PIN, payload[1] ? HIGH : LOW);
  }
}
