"""
ECG Monitor — Python Serial Reader
Reads real ECG data from Arduino + AD8232 sensor over USB serial.
Displays live scrolling waveform, detects R-peaks, estimates BPM,
and alerts on tachycardia or bradycardia.

Requirements:
    pip install pyserial numpy matplotlib

Usage:
    1. Upload ecg_monitor.ino to your Arduino
    2. Connect Arduino via USB
    3. Find your COM port:
         Windows:  Device Manager → Ports (COM & LPT) → e.g. COM3
         Mac/Linux: ls /dev/tty.*  or  ls /dev/ttyUSB*
    4. Set SERIAL_PORT below and run:
         python ecg_serial.py
"""

import serial
import serial.tools.list_ports
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import sys
import time

# ── Config ────────────────────────────────────────────────────────
SERIAL_PORT     = "COM3"       # Change to your port (e.g. "/dev/ttyUSB0" on Linux/Mac)
BAUD_RATE       = 115200       # Must match Arduino sketch
SAMPLE_RATE_HZ  = 250          # Samples per second (matches Arduino 4ms interval)
WINDOW_SECONDS  = 5            # Seconds of ECG data shown on screen
ADC_MAX         = 1023         # Arduino 10-bit ADC maximum
MIDPOINT        = 512          # Resting baseline from AD8232
SCALE_FACTOR    = 1.5          # Scales ADC range to ±1.5 mV display units

ALERT_HIGH_BPM  = 100          # Tachycardia threshold
ALERT_LOW_BPM   = 50           # Bradycardia threshold
LEAD_OFF_SENTINEL = 9999       # Sent by Arduino when electrodes disconnected

BUFFER_SIZE = SAMPLE_RATE_HZ * WINDOW_SECONDS
# ─────────────────────────────────────────────────────────────────


def find_arduino_port() -> str | None:
    """Auto-detect Arduino by scanning available serial ports."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if any(kw in (p.description or "").lower() for kw in ["arduino", "ch340", "cp210", "ftdi"]):
            print(f"  Auto-detected Arduino on {p.device} ({p.description})")
            return p.device
    return None


def normalize(raw_value: int) -> float:
    """Convert raw 10-bit ADC value to millivolt-scale float."""
    return (raw_value - MIDPOINT) / MIDPOINT * SCALE_FACTOR


def detect_beats(buffer: deque, sample_rate: int, threshold: float = 0.6) -> tuple[int, list]:
    """
    Simple threshold-based R-peak detector.
    Works by finding upward crossings above the threshold.
    Returns (estimated_bpm, list_of_peak_indices).
    """
    arr = np.array(buffer)
    peaks = []
    refractory = int(sample_rate * 0.25)   # 250ms refractory period between beats
    last_peak = -refractory
    in_peak = False

    for i in range(len(arr)):
        if arr[i] > threshold and not in_peak and (i - last_peak) > refractory:
            peaks.append(i)
            last_peak = i
            in_peak = True
        elif arr[i] < threshold * 0.4:
            in_peak = False

    if len(peaks) >= 2:
        rr_intervals = np.diff(peaks) / sample_rate          # seconds between beats
        bpm = int(60 / np.mean(rr_intervals))
    else:
        bpm = 0

    return bpm, peaks


def check_alerts(bpm: int, lead_off: bool) -> tuple[str, str]:
    """Returns (alert_message, color_hex)."""
    if lead_off:
        return "LEAD OFF — check electrode connections", "#ff9800"
    if bpm > ALERT_HIGH_BPM:
        return f"TACHYCARDIA  {bpm} bpm > {ALERT_HIGH_BPM} bpm", "#e24b4a"
    if 0 < bpm < ALERT_LOW_BPM:
        return f"BRADYCARDIA  {bpm} bpm < {ALERT_LOW_BPM} bpm", "#e24b4a"
    return "", "#2dcc6f"


# ── Serial connection ─────────────────────────────────────────────
def open_serial(port: str) -> serial.Serial:
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)          # Wait for Arduino to reset after serial connect
        ser.reset_input_buffer()
        print(f"  Connected to {port} at {BAUD_RATE} baud.")
        return ser
    except serial.SerialException as e:
        print(f"\n  ERROR: Could not open {port}\n  {e}")
        print("\n  Available ports:")
        for p in serial.tools.list_ports.comports():
            print(f"    {p.device}  —  {p.description}")
        sys.exit(1)


print("ECG Monitor — Hardware Mode")
print("─" * 40)

port = find_arduino_port() or SERIAL_PORT
ser  = open_serial(port)


# ── Plot setup ────────────────────────────────────────────────────
ecg_buffer  = deque([0.0] * BUFFER_SIZE, maxlen=BUFFER_SIZE)
peak_buffer = deque([0.0] * BUFFER_SIZE, maxlen=BUFFER_SIZE)   # for peak markers
lead_off    = False

fig, ax = plt.subplots(figsize=(13, 4), facecolor='#0a0a0a')
ax.set_facecolor('#0a0a0a')
ax.tick_params(colors='#555', labelsize=8)
ax.spines[:].set_color('#1a1a1a')
ax.set_ylim(-1.8, 2.2)
ax.set_xlim(0, BUFFER_SIZE)
ax.set_xlabel("Samples  (250 Hz = 1 sec per 250 units)", color='#555', fontsize=8)
ax.set_ylabel("Amplitude (mV)", color='#555', fontsize=8)
ax.set_title(f"ECG Monitor — {port}  |  AD8232 + Arduino", color='#2dcc6f', fontsize=10, pad=8)

# ECG paper grid
for x in range(0, BUFFER_SIZE, SAMPLE_RATE_HZ):       # 1-second major grid
    ax.axvline(x, color='#1a2a1a', linewidth=0.8)
for x in range(0, BUFFER_SIZE, SAMPLE_RATE_HZ // 5):  # 200ms minor grid
    ax.axvline(x, color='#111a11', linewidth=0.3)
ax.axhline(0, color='#1a2a1a', linewidth=0.5)

ecg_line,   = ax.plot([], [], color='#2dcc6f', linewidth=1.2, zorder=3)
peak_marks, = ax.plot([], [], 'o', color='#ff6b6b', markersize=4, zorder=4, alpha=0.8)

alert_text = ax.text(20,    1.9, '', color='#e24b4a', fontsize=10, fontweight='bold', zorder=5)
bpm_text   = ax.text(BUFFER_SIZE - 320, 1.9, '', color='#2dcc6f', fontsize=13, fontweight='bold', zorder=5)
time_text  = ax.text(20,   -1.5, '', color='#444',   fontsize=8,  zorder=5)

x_data = np.arange(BUFFER_SIZE)


# ── Animation update ──────────────────────────────────────────────
def update(frame):
    global lead_off

    # Drain all bytes waiting in the serial buffer this frame
    bytes_waiting = ser.in_waiting
    lines_to_read = max(1, bytes_waiting // 6)   # ~6 bytes per "NNNN\r\n"

    for _ in range(min(lines_to_read, 20)):
        try:
            raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not raw_line:
                continue
            value = int(raw_line)

            if value == LEAD_OFF_SENTINEL:
                lead_off = True
                ecg_buffer.append(0.0)
            else:
                lead_off = False
                ecg_buffer.append(normalize(value))

        except (ValueError, serial.SerialException):
            pass   # Skip malformed lines silently

    # Update waveform
    data = list(ecg_buffer)
    ecg_line.set_data(x_data, data)

    # Detect beats and mark peaks
    bpm, peak_indices = detect_beats(ecg_buffer, SAMPLE_RATE_HZ)
    if peak_indices:
        px = [p for p in peak_indices if p < len(data)]
        py = [data[p] for p in px]
        peak_marks.set_data(px, py)
    else:
        peak_marks.set_data([], [])

    # Update text overlays
    alert_msg, alert_color = check_alerts(bpm, lead_off)
    alert_text.set_text(alert_msg)
    alert_text.set_color(alert_color)
    bpm_text.set_text(f"HR: {bpm} bpm" if bpm > 0 and not lead_off else "")
    time_text.set_text(f"Port: {port}  |  {SAMPLE_RATE_HZ} Hz  |  {WINDOW_SECONDS}s window")

    return ecg_line, peak_marks, alert_text, bpm_text, time_text


ani = animation.FuncAnimation(
    fig, update,
    interval=33,       # ~30 fps
    blit=True,
    cache_frame_data=False
)

plt.tight_layout()

try:
    plt.show()
finally:
    ser.close()
    print("\nSerial port closed.")
