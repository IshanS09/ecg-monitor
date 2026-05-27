const int ECG_PIN   = A0;
const int LO_PLUS   = 10;
const int LO_MINUS  = 11;

const unsigned int SAMPLE_INTERVAL_MS = 4;

unsigned long lastSampleTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(LO_PLUS,  INPUT);
  pinMode(LO_MINUS, INPUT);
  delay(100);
}

void loop() {
  unsigned long now = millis();

  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;

    if (digitalRead(LO_PLUS) == HIGH || digitalRead(LO_MINUS) == HIGH) {
      Serial.println(9999);
    } else {
      int ecgValue = analogRead(ECG_PIN);
      Serial.println(ecgValue);
    }
  }
}