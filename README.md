# ECG Monitor
### Real-time electrocardiogram — AD8232 + Arduino + Python + Web Dashboard

A complete ECG monitor built from scratch that captures electrical signals from the human heart, displays a live scrolling waveform in a web browser, detects heartbeats, estimates BPM, runs real-time anomaly detection, and shows vitals on a standalone OLED screen.

Built as Research Officer at **Heart of Gold**, a student-led nonprofit focused on cardiovascular health research.

---

## Demo

![Web Dashboard]
*Live web dashboard — 55 BPM, clean QRS waveform, anomaly detector active*

![OLED Display]
*Standalone OLED showing live BPM and mini ECG waveform*

---

## Features

- Captures cardiac electrical signals at **250 Hz** via AD8232 biopotential sensor
- **Live web dashboard** served via Flask + SocketIO — viewable on any device on your WiFi
- **Real-time anomaly detection** — trains on first 30 beats, then flags irregular patterns
- **OLED display** showing BPM, rhythm status, and scrolling mini waveform — no computer needed
- **LED heartbeat indicator** — flashes physically with every detected beat
- **BPM history graph** — 60-reading trend line
- **QRS complex zoom** — last beat pattern displayed in real time
- **Session statistics** — avg BPM, min/max, total beats, anomaly count
- **CSV data logger** — record sessions with timestamp, mV, BPM, anomaly flag
- **Lead-off detection** — alerts when electrode disconnects
- Tachycardia (>100 bpm) and bradycardia (<50 bpm) alerts

---

## Hardware

| Component | Purpose | Cost |
|-----------|---------|------|
| Arduino Uno R3 | Microcontroller — samples sensor, streams serial data | ~$28 |
| AD8232 ECG Sensor Module | Amplifies and filters cardiac biopotential signals | ~$12 |
| SSD1306 OLED 128x64 (I2C) | Standalone BPM + waveform display | ~$8 |
| Green LED + 220Ω resistor | Physical heartbeat flash indicator | ~$1 |
| Disposable ECG electrode pads (x3) | Medical grade skin contact | ~$5 |
| Jumper wires + breadboard | Circuit connections | ~$10 |
| USB-A to USB-B cable | Arduino to computer | ~$8 |

**Total: ~$72**

---

## Wiring

### AD8232 → Arduino

| AD8232 Pin | Arduino Pin |
|------------|-------------|
| GND | GND |
| 3.3V | 3.3V |
| OUTPUT | A0 |
| LO- | D11 |
| LO+ | D10 |

### OLED SSD1306 → Arduino (I2C)

| OLED Pin | Arduino Pin |
|----------|-------------|
| GND | GND |
| VCC | 5V |
| SCL | A5 |
| SDA | A4 |

### LED

```
Arduino D13 → 220Ω resistor → LED positive leg (long)
LED negative leg (short) → Arduino GND
```

> ⚠️ Use Arduino **3.3V** for AD8232 — NOT 5V. 5V will permanently damage the module.

---

## Electrode Placement

| Lead | Position |
|------|----------|
| RA (Red) | Right collarbone / inner right wrist |
| LA (Yellow) | Left collarbone / inner left wrist |
| RL (Teal) | Lower left ribcage (ground reference) |

**Tips for clean signal:**
- Use medical grade ECG pads (Kendall/Covidien recommended)
- Press each pad firmly for 10 seconds
- Run laptop on battery — charger introduces 60Hz AC noise
- Sit completely still during readings

---

## Software

### Requirements

```bash
pip3 install pyserial numpy matplotlib flask flask-socketio scikit-learn
```

### Arduino Libraries (install via Arduino IDE Library Manager)
- Adafruit SSD1306
- Adafruit GFX Library

---

## Setup & Run

### Option 1 — Web Dashboard (recommended)

```bash
# 1. Upload ecg_monitor_v2.ino to Arduino via Arduino IDE
# 2. Quit Arduino IDE completely
# 3. Edit server.py line 20 — set your serial port:
#    SERIAL_PORT = "/dev/cu.usbmodem14101"
# 4. Run:
cd ecg_dashboard
python3 server.py
# 5. Open browser: http://localhost:8080
# 6. View on phone/tablet: http://YOUR_MAC_IP:8080
```

### Option 2 — Matplotlib (simple, no server)

```bash
# 1. Upload ecg_monitor.ino to Arduino
# 2. Edit ecg_serial.py — set your serial port
# 3. Run:
python3 ecg_serial.py
```

---

## Finding Your Serial Port

- **Mac:** `ls /dev/tty.*` in Terminal → look for `/dev/cu.usbmodem...`
- **Linux:** `ls /dev/ttyUSB*`
- **Windows:** Device Manager → Ports → COM3, COM4, etc.

---

## File Structure

```
ecg-monitor/
├── ecg_monitor.ino          # Arduino sketch v1 — basic serial streaming
├── ecg_monitor_v2.ino       # Arduino sketch v2 — adds OLED + LED
├── ecg_serial.py            # Python matplotlib live plot
├── ecg_dashboard/
│   ├── server.py            # Flask + SocketIO web dashboard server
│   └── templates/
│       └── index.html       # Dashboard UI
└── README.md
```

---

## How It Works

### Arduino
Samples the AD8232 OUTPUT pin every **4ms** (250 Hz) using `millis()` for precise timing. Checks lead-off detection pins each sample. Streams raw 10-bit ADC values (0–1023) over USB serial at 115200 baud. Simultaneously drives the OLED display at 10Hz with BPM and mini waveform, and flashes the LED on each detected beat.

### Python Server
Reads the serial stream and normalizes ADC values to millivolt scale. Maintains a 5-second rolling buffer rendered as a live scrolling waveform at ~30fps via WebSocket. Threshold-based R-peak detector with 250ms refractory period identifies beats. BPM calculated from average R-R interval across last 10 beats.

### Anomaly Detector
Collects the first 30 heartbeat waveforms (60-sample windows around each R-peak) as normal training data. Computes mean and standard deviation of the training set. Each subsequent beat is scored by average z-score against the training distribution. Beats exceeding the threshold are flagged as anomalous and highlighted red in the dashboard.

### ECG Wave Anatomy
Each heartbeat produces three visible features:
- **P wave** — small bump before spike; atrial depolarization
- **QRS complex** — tall sharp spike; ventricular depolarization (heart pumping)
- **T wave** — broad bump after spike; ventricular repolarization

---

## Real-World Engineering Challenges Encountered

- **60Hz AC noise** from laptop charger introduced false beat detections — solved by running on battery power
- **Electrode contact quality** — dry or old pads produced weak signals; medical grade hydrogel pads resolved this
- **Beat detection threshold calibration** — threshold tuned empirically to sit above noise floor but below R-peak amplitude
- **Serial port contention** — Arduino IDE and Python cannot share the serial port simultaneously

---

## Future Work

- [ ] Heart rate variability (HRV) — SDNN and RMSSD metrics
- [ ] Custom PCB to replace breadboard
- [ ] 3D printed enclosure (Fusion 360)
- [ ] Raspberry Pi port for fully wireless standalone operation
- [ ] ML beat classifier trained on labelled arrhythmia datasets
- [ ] SpO2 monitoring via MAX30102 sensor

---

## Safety Note

Educational device only — not a medical instrument. AD8232 operates at 3.3V, safe for skin contact. USB power only. Do not use on anyone with a pacemaker or cardiac condition.

---

## About

Built by **Ishan Singh**, Research Officer at **Heart of Gold**
Student-led nonprofit dedicated to cardiovascular health research and education
Frisco, TX — 2026
