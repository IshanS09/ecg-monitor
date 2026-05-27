#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

const int ECG_PIN  = A0;
const int LO_PLUS  = 10;
const int LO_MINUS = 11;
const int LED_PIN  = 13;

const unsigned int SAMPLE_INTERVAL_MS  = 4;
const unsigned int DISPLAY_INTERVAL_MS = 100;
unsigned long lastSampleTime  = 0;
unsigned long lastDisplayTime = 0;

const int          THRESHOLD      = 600;
const unsigned long REFRACTORY_MS = 250;
unsigned long lastBeatTime = 0;
bool inBeat = false;

unsigned long beatTimestamps[8];
int beatHead  = 0;
int beatCount = 0;
int currentBPM = 0;

const int WAVE_LEN = 64;
int waveBuffer[WAVE_LEN];
int waveHead = 0;

bool leadOff = false;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(LO_PLUS,  INPUT);
  pinMode(LO_MINUS, INPUT);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found");
  } else {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(20, 20);
    display.println("Heart of Gold");
    display.setCursor(28, 35);
    display.println("ECG Monitor");
    display.display();
    delay(1500);
    display.clearDisplay();
  }

  delay(100);
}

void loop() {
  unsigned long now = millis();

  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;

    if (digitalRead(LO_PLUS) == HIGH || digitalRead(LO_MINUS) == HIGH) {
      leadOff = true;
      Serial.println(9999);
      digitalWrite(LED_PIN, LOW);
    } else {
      leadOff = false;
      int ecgValue = analogRead(ECG_PIN);
      Serial.println(ecgValue);

      waveBuffer[waveHead] = ecgValue;
      waveHead = (waveHead + 1) % WAVE_LEN;

      if (ecgValue > THRESHOLD && !inBeat &&
          (now - lastBeatTime) > REFRACTORY_MS) {
        inBeat = true;
        lastBeatTime = now;

        digitalWrite(LED_PIN, HIGH);

        beatTimestamps[beatHead % 8] = now;
        beatHead++;
        if (beatCount < 8) beatCount++;

        if (beatCount >= 2) {
          int n = min(beatCount, 8);
          unsigned long oldest = beatTimestamps[(beatHead - n + 8) % 8];
          unsigned long newest = beatTimestamps[(beatHead - 1 + 8) % 8];
          float avgInterval = (float)(newest - oldest) / (n - 1);
          currentBPM = (int)(60000.0 / avgInterval);
          if (currentBPM < 30 || currentBPM > 220) currentBPM = 0;
        }

      } else if (ecgValue < THRESHOLD - 50) {
        inBeat = false;
        digitalWrite(LED_PIN, LOW);
      }
    }
  }

  if (now - lastDisplayTime >= DISPLAY_INTERVAL_MS) {
    lastDisplayTime = now;
    updateDisplay();
  }
}

void updateDisplay() {
  display.clearDisplay();

  if (leadOff) {
    display.setTextSize(1);
    display.setCursor(20, 10);
    display.println("!! LEAD OFF !!");
    display.setCursor(8, 25);
    display.println("Check electrodes");
    display.setCursor(16, 40);
    display.println("and re-press pads");
    display.display();
    return;
  }

  display.setTextSize(3);
  display.setCursor(0, 0);
  if (currentBPM > 0) {
    display.print(currentBPM);
  } else {
    display.print("---");
  }

  display.setTextSize(1);
  display.setCursor(0, 26);
  display.print("BPM");

  display.setCursor(80, 0);
  display.setTextSize(1);
  if (currentBPM > 100) {
    display.println("TACHY");
  } else if (currentBPM > 0 && currentBPM < 50) {
    display.println("BRADY");
  } else if (currentBPM > 0) {
    display.println("NORMAL");
  } else {
    display.println("------");
  }

  display.setCursor(108, 12);
  display.print("<3");

  display.drawFastHLine(0, 36, 128, SSD1306_WHITE);

  for (int i = 0; i < WAVE_LEN - 1; i++) {
    int idx0 = (waveHead + i)     % WAVE_LEN;
    int idx1 = (waveHead + i + 1) % WAVE_LEN;
    int y0 = 63 - map(waveBuffer[idx0], 300, 700, 38, 63);
    int y1 = 63 - map(waveBuffer[idx1], 300, 700, 38, 63);
    y0 = constrain(y0, 37, 63);
    y1 = constrain(y1, 37, 63);
    int x0 = i * 2;
    int x1 = (i + 1) * 2;
    display.drawLine(x0, y0, x1, y1, SSD1306_WHITE);
  }

  display.display();
}