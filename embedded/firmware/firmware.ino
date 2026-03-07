#include <ESP_I2S.h>
#include <stdint.h>

// Frame types (must match backend/nodes/serial_node.py)
constexpr uint8_t FRAME_AUDIO     = 0x01;
constexpr uint8_t FRAME_BUTTON    = 0x02;
constexpr uint8_t FRAME_AUDIO_OUT = 0x81;
constexpr uint8_t FRAME_LED       = 0x82;

// Microphone config (XIAO ESP32S3 Sense built-in PDM mic)
constexpr int MIC_CLK_PIN  = 42;
constexpr int MIC_DATA_PIN = 41;
constexpr int SAMPLE_RATE  = 16000;

// Audio buffer: 512 samples = 1024 bytes = 32ms at 16kHz
constexpr int AUDIO_BUF_SAMPLES = 512;
int16_t audioBuf[AUDIO_BUF_SAMPLES];

constexpr int LED_PIN = 21;  // XIAO ESP32S3 built-in LED

I2SClass i2s;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);  // LED is active-low on XIAO ESP32S3

  // Configure PDM microphone
  i2s.setPinsPdmRx(MIC_CLK_PIN, MIC_DATA_PIN);
  if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    // Flash LED rapidly to indicate error
    while (true) {
      digitalWrite(LED_PIN, LOW);
      delay(100);
      digitalWrite(LED_PIN, HIGH);
      delay(100);
    }
  }
}

void sendFrame(uint8_t frameType, const uint8_t *payload, uint16_t length) {
  uint8_t header[3];
  header[0] = frameType;
  header[1] = (length >> 8) & 0xFF;
  header[2] = length & 0xFF;
  Serial.write(header, 3);
  Serial.write(payload, length);
}

void readMicrophone() {
  size_t bytesRead = i2s.readBytes((char *)audioBuf, sizeof(audioBuf));
  if (bytesRead > 0) {
    sendFrame(FRAME_AUDIO, (const uint8_t *)audioBuf, bytesRead);
  }
}

void handleIncoming() {
  while (Serial.available() >= 3) {
    uint8_t frameType = Serial.read();
    uint8_t lenHi     = Serial.read();
    uint8_t lenLo     = Serial.read();
    uint16_t length   = (uint16_t(lenHi) << 8) | lenLo;

    uint8_t payload[256];
    uint16_t toRead = min(length, (uint16_t)sizeof(payload));
    uint16_t got = 0;
    unsigned long start = millis();
    while (got < toRead && (millis() - start) < 100) {
      if (Serial.available()) {
        payload[got++] = Serial.read();
      }
    }
    // Discard extra bytes beyond buffer
    for (uint16_t i = got; i < length; i++) {
      while (!Serial.available() && (millis() - start) < 100) {}
      if (Serial.available()) Serial.read();
    }

    if (got < toRead) continue;

    if (frameType == FRAME_LED && got >= 2) {
      // payload[1]: 1 = on, 0 = off (active-low LED)
      digitalWrite(LED_PIN, payload[1] ? LOW : HIGH);
    }
  }
}

void loop() {
  readMicrophone();
  handleIncoming();
}
