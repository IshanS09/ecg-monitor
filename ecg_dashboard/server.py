"""
ECG Monitor — Web Dashboard Server
====================================
Flask + SocketIO server that reads ECG data from Arduino,
runs anomaly detection, and streams everything to a browser dashboard.

Requirements:
    pip3 install flask flask-socketio eventlet pyserial numpy scikit-learn

Usage:
    1. Upload ecg_monitor.ino to Arduino
    2. Set SERIAL_PORT below to your port
    3. Run: python3 server.py
    4. Open browser: http://localhost:5000
"""

import time
import threading
import csv
import os
from collections import deque
from datetime import datetime

import numpy as np
import serial
import serial.tools.list_ports
from flask import Flask, render_template, send_file
from flask_socketio import SocketIO

# ── Config ────────────────────────────────────────────────────────
SERIAL_PORT       = "/dev/cu.usbmodem11201"  # ← change to your port
BAUD_RATE         = 115200
SAMPLE_RATE_HZ    = 250
WINDOW_SECONDS    = 5
MIDPOINT          = 512
SCALE_FACTOR      = 1.5
ALERT_HIGH_BPM    = 100
ALERT_LOW_BPM     = 50
LEAD_OFF_SENTINEL = 9999

# Anomaly detection config
BEAT_WINDOW       = 60        # samples around each R-peak to extract as feature
TRAIN_BEATS       = 30        # number of normal beats to collect before training
ANOMALY_THRESHOLD = 0.15      # reconstruction error threshold

BUFFER_SIZE = SAMPLE_RATE_HZ * WINDOW_SECONDS

# ── App setup ─────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ecg_heart_of_gold'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

# ── Shared state ──────────────────────────────────────────────────
ecg_buffer    = deque([0.0] * BUFFER_SIZE, maxlen=BUFFER_SIZE)
bpm_history   = deque(maxlen=60)       # last 60 BPM readings
beat_times    = deque(maxlen=200)      # timestamps of detected beats
session_start = time.time()
lead_off      = False
current_bpm   = 0
session_beats = 0
anomaly_count = 0
recording     = False
csv_rows      = []

# Anomaly detector state
normal_beats      = []      # collected normal beat waveforms
detector_trained  = False
detector_mean     = None
detector_std      = None

# ── Serial ────────────────────────────────────────────────────────
def find_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if any(kw in (p.description or "").lower()
               for kw in ["arduino", "ch340", "cp210", "ftdi"]):
            print(f"  Auto-detected: {p.device}")
            return p.device
    return SERIAL_PORT

def normalize(raw):
    return (raw - MIDPOINT) / MIDPOINT * SCALE_FACTOR

# ── Beat detection ────────────────────────────────────────────────
last_peak_idx   = -999
refractory      = int(SAMPLE_RATE_HZ * 0.25)

def detect_beat(buffer_arr, new_idx, threshold=0.5):
    global last_peak_idx
    val = buffer_arr[new_idx % len(buffer_arr)]
    if val > threshold and (new_idx - last_peak_idx) > refractory:
        last_peak_idx = new_idx
        return True
    return False

def compute_bpm():
    if len(beat_times) < 2:
        return 0
    recent = list(beat_times)[-10:]
    if len(recent) < 2:
        return 0
    intervals = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
    avg_interval = sum(intervals) / len(intervals)
    return int(60 / avg_interval) if avg_interval > 0 else 0

# ── Anomaly detection ─────────────────────────────────────────────
def extract_beat_window(buffer_arr, peak_idx, half=30):
    arr = list(buffer_arr)
    n   = len(arr)
    start = max(0, peak_idx - half)
    end   = min(n, peak_idx + half)
    window = arr[start:end]
    if len(window) < half * 2:
        window = window + [0.0] * (half * 2 - len(window))
    return np.array(window[:half*2])

def train_detector(beats):
    global detector_trained, detector_mean, detector_std
    mat = np.array(beats)
    detector_mean = mat.mean(axis=0)
    detector_std  = mat.std(axis=0) + 1e-6
    detector_trained = True
    print(f"  Anomaly detector trained on {len(beats)} normal beats.")

def score_beat(window):
    if not detector_trained:
        return 0.0
    z = np.abs((window - detector_mean) / detector_std)
    return float(z.mean())

# ── CSV logging ───────────────────────────────────────────────────
def save_csv():
    fname = f"ecg_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fname, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['timestamp_ms', 'ecg_mv', 'bpm', 'anomaly'])
        w.writerows(csv_rows)
    return fname

# ── Main serial read loop ─────────────────────────────────────────
def serial_loop():
    global lead_off, current_bpm, session_beats, anomaly_count, recording

    port = find_port()
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)
        ser.reset_input_buffer()
        print(f"  Connected to {port}")
    except serial.SerialException as e:
        print(f"  ERROR: {e}")
        return

    sample_idx   = 0
    buffer_arr   = list(ecg_buffer)
    emit_counter = 0
    EMIT_EVERY   = 5   # emit to browser every N samples (~50fps at 250Hz)

    while True:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue
            raw = int(line)

            if raw == LEAD_OFF_SENTINEL:
                lead_off = True
                val = 0.0
            else:
                lead_off = False
                val = normalize(raw)

            ecg_buffer.append(val)
            buffer_arr = list(ecg_buffer)
            ts = time.time()

            # Beat detection
            is_beat   = detect_beat(buffer_arr, sample_idx, threshold=0.2)
            is_anomaly = False

            if is_beat and not lead_off:
                beat_times.append(ts)
                session_beats += 1
                current_bpm = compute_bpm()
                bpm_history.append(current_bpm)

                # Anomaly detection
                window = extract_beat_window(buffer_arr,
                                             sample_idx % len(buffer_arr))
                if not detector_trained:
                    normal_beats.append(window)
                    if len(normal_beats) >= TRAIN_BEATS:
                        train_detector(normal_beats)
                else:
                    score = score_beat(window)
                    if score > ANOMALY_THRESHOLD:
                        is_anomaly = True
                        anomaly_count += 1

            # CSV recording
            if recording:
                csv_rows.append([
                    int((ts - session_start) * 1000),
                    round(val, 4),
                    current_bpm,
                    1 if is_anomaly else 0
                ])

            sample_idx += 1
            emit_counter += 1

            # Emit to browser
            if emit_counter >= EMIT_EVERY:
                emit_counter = 0
                elapsed = ts - session_start
                mm = int(elapsed // 60)
                ss = int(elapsed % 60)

                socketio.emit('ecg_data', {
                    'samples':      list(ecg_buffer)[-50:],
                    'bpm':          current_bpm,
                    'bpm_history':  list(bpm_history),
                    'lead_off':     lead_off,
                    'is_beat':      is_beat,
                    'is_anomaly':   is_anomaly,
                    'session_beats': session_beats,
                    'anomaly_count': anomaly_count,
                    'trained':      detector_trained,
                    'train_progress': min(100, int(len(normal_beats) / TRAIN_BEATS * 100)),
                    'elapsed':      f"{mm:02d}:{ss:02d}",
                    'recording':    recording,
                })

        except (ValueError, serial.SerialException):
            pass
        except Exception as e:
            print(f"  Loop error: {e}")

# ── Routes ────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download():
    fname = save_csv()
    return send_file(fname, as_attachment=True)

@socketio.on('toggle_record')
def toggle_record():
    global recording
    recording = not recording
    if not recording and csv_rows:
        save_csv()
        print(f"  Saved {len(csv_rows)} rows to CSV.")

@socketio.on('connect')
def on_connect():
    print("  Browser connected.")

# ── Start ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    t = threading.Thread(target=serial_loop, daemon=True)
    t.start()
    print("\nECG Dashboard running at http://localhost:5000\n")
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
