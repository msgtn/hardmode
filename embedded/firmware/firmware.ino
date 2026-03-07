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

// Audio input buffer: 512 samples = 1024 bytes = 32ms at 16kHz
constexpr int AUDIO_BUF_SAMPLES = 512;
int16_t micBuf[AUDIO_BUF_SAMPLES];

constexpr int LED_PIN = 21;  // XIAO ESP32S3 built-in LED

// Audio output via I2S PDM TX (hardware-timed, DMA-buffered)
constexpr int SPK_CLK_PIN  = 3;  // GPIO3 (D2/A2) — PDM clock (not needed externally)
constexpr int SPK_DATA_PIN = 2;  // GPIO2 (D1/A1) — PDM data, low-pass filter to speaker

// Mutex for Serial writes (mic task and main loop both write)
SemaphoreHandle_t serialMutex;

// Pause mic during audio playback to avoid concurrent Serial access
volatile bool micPaused = false;

I2SClass i2sIn;   // mic input (auto-assigns I2S port)
I2SClass i2sOut;  // speaker output (auto-assigns I2S port)

void sendFrame(uint8_t frameType, const uint8_t *payload, uint16_t length) {
  uint8_t header[3];
  header[0] = frameType;
  header[1] = (length >> 8) & 0xFF;
  header[2] = length & 0xFF;
  xSemaphoreTake(serialMutex, portMAX_DELAY);
  Serial.write(header, 3);
  Serial.write(payload, length);
  xSemaphoreGive(serialMutex);
}

// Mic task: reads I2S and sends frames, pauses during audio playback
void micTask(void *param) {
  while (true) {
    if (micPaused) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    size_t bytesRead = i2sIn.readBytes((char *)micBuf, sizeof(micBuf));
    if (bytesRead > 0) {
      sendFrame(FRAME_AUDIO, (const uint8_t *)micBuf, bytesRead);
    }
  }
}

void handleIncoming() {
  while (Serial.available() >= 3) {
    uint8_t frameType = Serial.read();
    uint8_t lenHi     = Serial.read();
    uint8_t lenLo     = Serial.read();
    uint16_t length   = (uint16_t(lenHi) << 8) | lenLo;

    if (frameType == FRAME_AUDIO_OUT) {
      micPaused = true;
      // Read payload and write directly to I2S output (DMA handles timing)
      uint8_t chunk[512];
      uint16_t remaining = length;
      unsigned long start = millis();
      while (remaining > 0 && (millis() - start) < 5000) {
        uint16_t toRead = min(remaining, (uint16_t)sizeof(chunk));
        uint16_t got = 0;
        while (got < toRead && (millis() - start) < 5000) {
          if (Serial.available()) {
            chunk[got++] = Serial.read();
          }
        }
        if (got > 0) {
          // Ensure even byte count for 16-bit samples
          uint16_t even = got & ~1;
          if (even > 0) {
            i2sOut.write(chunk, even);
          }
          remaining -= got;
        }
      }
      continue;
    }

    uint8_t payload[256];
    uint16_t toRead = min(length, (uint16_t)sizeof(payload));
    uint16_t got = 0;
    unsigned long start = millis();
    while (got < toRead && (millis() - start) < 100) {
      if (Serial.available()) {
        payload[got++] = Serial.read();
      }
    }
    for (uint16_t i = got; i < length; i++) {
      while (!Serial.available() && (millis() - start) < 100) {}
      if (Serial.available()) Serial.read();
    }
    if (got < toRead) continue;

    if (frameType == FRAME_LED && got >= 2) {
      digitalWrite(LED_PIN, payload[1] ? LOW : HIGH);
    }
  }
}

void setup() {
  Serial.setRxBufferSize(16384);
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  serialMutex = xSemaphoreCreateMutex();

  // Configure PDM microphone (I2S0)
  i2sIn.setPinsPdmRx(MIC_CLK_PIN, MIC_DATA_PIN);
  if (!i2sIn.begin(I2S_MODE_PDM_RX, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    while (true) {
      digitalWrite(LED_PIN, LOW);
      delay(100);
      digitalWrite(LED_PIN, HIGH);
      delay(100);
    }
  }

  // Configure PDM speaker output (I2S1)
  i2sOut.setPinsPdmTx(SPK_CLK_PIN, SPK_DATA_PIN);
  if (!i2sOut.begin(I2S_MODE_PDM_TX, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    while (true) {
      digitalWrite(LED_PIN, LOW);
      delay(50);
      digitalWrite(LED_PIN, HIGH);
      delay(50);
    }
  }

  // Mic capture on core 1
  xTaskCreatePinnedToCore(micTask, "mic", 4096, NULL, 3, NULL, 1);
}

// Main loop (core 1): dedicated to servicing incoming serial
void loop() {
  handleIncoming();
  // Unpause mic when I2S output buffer is drained
  if (micPaused && i2sOut.available() == 0) {
    micPaused = false;
  }
}
