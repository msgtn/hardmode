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

// Audio output via PWM
constexpr int AUDIO_OUT_PIN = 2;   // GPIO2 (D1/A1) — connect speaker/amplifier here
constexpr int PWM_FREQ      = 40000;  // 40kHz carrier, well above audible range
constexpr int PWM_RESOLUTION = 8;     // 8-bit duty cycle (0–255)

// Ring buffer for audio output playback
constexpr int RING_BUF_SIZE = 65536;  // ~4s at 16kHz
volatile int16_t ringBuf[RING_BUF_SIZE];
volatile int ringHead = 0;  // written by main loop (core 1)
volatile int ringTail = 0;  // read by audio task (core 0)

// Mutex for Serial writes (mic task and main loop both write)
SemaphoreHandle_t serialMutex;

I2SClass i2s;

// Audio output task: runs on core 0, outputs samples at exactly 16kHz via PWM.
void audioOutputTask(void *param) {
  int64_t nextSampleTimeX2 = esp_timer_get_time() * 2;

  while (true) {
    int64_t nowX2 = esp_timer_get_time() * 2;
    if (nowX2 < nextSampleTimeX2) {
      delayMicroseconds((nextSampleTimeX2 - nowX2) / 2);
    }
    nextSampleTimeX2 += 125;  // 62.5μs * 2 = 125 half-μs

    if (ringHead != ringTail) {
      int16_t sample = ringBuf[ringTail];
      ringTail = (ringTail + 1) % RING_BUF_SIZE;
      uint8_t duty = (uint8_t)((sample + 32768) >> 8);
      ledcWrite(AUDIO_OUT_PIN, duty);
    } else {
      ledcWrite(AUDIO_OUT_PIN, 128);
    }
  }
}

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

// Mic task: runs on core 0, reads I2S and sends frames (non-blocking to main loop)
void micTask(void *param) {
  while (true) {
    size_t bytesRead = i2s.readBytes((char *)micBuf, sizeof(micBuf));
    if (bytesRead > 0) {
      sendFrame(FRAME_AUDIO, (const uint8_t *)micBuf, bytesRead);
    }
  }
}

// Queue 16-bit PCM samples into the ring buffer for playback
void queueAudioOut(const uint8_t *data, uint16_t length) {
  uint16_t numSamples = length / 2;
  const int16_t *samples = (const int16_t *)data;
  for (uint16_t i = 0; i < numSamples; i++) {
    int nextHead = (ringHead + 1) % RING_BUF_SIZE;
    if (nextHead == ringTail) break;
    ringBuf[ringHead] = samples[i];
    ringHead = nextHead;
  }
}

void handleIncoming() {
  while (Serial.available() >= 3) {
    uint8_t frameType = Serial.read();
    uint8_t lenHi     = Serial.read();
    uint8_t lenLo     = Serial.read();
    uint16_t length   = (uint16_t(lenHi) << 8) | lenLo;

    if (frameType == FRAME_AUDIO_OUT) {
      uint8_t chunk[256];
      uint16_t remaining = length;
      unsigned long start = millis();
      while (remaining > 0 && (millis() - start) < 500) {
        uint16_t toRead = min(remaining, (uint16_t)sizeof(chunk));
        uint16_t got = 0;
        while (got < toRead && (millis() - start) < 500) {
          if (Serial.available()) {
            chunk[got++] = Serial.read();
          }
        }
        if (got > 0) {
          queueAudioOut(chunk, got);
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

  // Configure PDM microphone
  i2s.setPinsPdmRx(MIC_CLK_PIN, MIC_DATA_PIN);
  if (!i2s.begin(I2S_MODE_PDM_RX, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)) {
    while (true) {
      digitalWrite(LED_PIN, LOW);
      delay(100);
      digitalWrite(LED_PIN, HIGH);
      delay(100);
    }
  }

  // Configure PWM audio output
  ledcAttach(AUDIO_OUT_PIN, PWM_FREQ, PWM_RESOLUTION);
  ledcWrite(AUDIO_OUT_PIN, 128);

  // Audio playback on core 0
  xTaskCreatePinnedToCore(audioOutputTask, "audio_out", 2048, NULL, 5, NULL, 0);
  // Mic capture on core 1 (core 0 is busy with audio output spin loop)
  xTaskCreatePinnedToCore(micTask, "mic", 4096, NULL, 3, NULL, 1);
}

// Main loop (core 1): dedicated to servicing incoming serial without blocking
void loop() {
  handleIncoming();
}
