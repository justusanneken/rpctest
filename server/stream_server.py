# RPC Surveillance Server

from flask import Flask, Response, render_template, request, jsonify, send_from_directory
import time
import cv2
import numpy as np
import threading
import os
from datetime import datetime

app = Flask(__name__)

# Directories
BASE_DIR      = os.path.dirname(__file__)
SNAPSHOT_DIR  = os.path.join(BASE_DIR, 'snapshots')
RECORDING_DIR = os.path.join(BASE_DIR, 'recordings')
os.makedirs(SNAPSHOT_DIR,  exist_ok=True)
os.makedirs(RECORDING_DIR, exist_ok=True)

# State
latest_photo       = None
motion_detected    = False
motion_enabled     = True
auto_snapshot      = False
previous_frame     = None
motion_sensitivity = 3000
stream_quality     = 80
frame_count        = 0
server_start_time  = time.time()
event_log          = []
recording          = False
record_writer      = None
record_lock        = threading.Lock()
last_auto_snap     = 0

# ── helpers ──────────────────────────────────────────────────────────────────

def add_event(kind, detail=""):
    ts = datetime.now().strftime("%H:%M:%S")
    event_log.append({"time": ts, "type": kind, "detail": detail})
    if len(event_log) > 200:
        event_log.pop(0)

def save_snapshot(frame_data, reason="manuell"):
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"snap_{ts}.jpg"
    with open(os.path.join(SNAPSHOT_DIR, filename), 'wb') as f:
        f.write(frame_data)
    add_event("snapshot", f"{reason} → {filename}")
    return filename

# ── motion detection loop ────────────────────────────────────────────────────

def detection_loop():
    global motion_detected, previous_frame, last_auto_snap
    while True:
        frame_data = latest_photo
        if frame_data:
            arr   = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                grey = cv2.GaussianBlur(grey, (21, 21), 0)
                if previous_frame is None:
                    previous_frame = grey
                else:
                    diff            = cv2.absdiff(previous_frame, grey)
                    _, thresh       = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                    changed_pixels  = cv2.countNonZero(thresh)
                    was_detected    = motion_detected
                    motion_detected = motion_enabled and changed_pixels > motion_sensitivity
                    if motion_detected and not was_detected:
                        add_event("motion", f"{changed_pixels} px verändert")
                        if auto_snapshot and (time.time() - last_auto_snap > 5):
                            save_snapshot(frame_data, "auto")
                            last_auto_snap = time.time()
                    previous_frame = grey
        time.sleep(0.2)

threading.Thread(target=detection_loop, daemon=True).start()

# ── routes ───────────────────────────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
def upload():
    global latest_photo, frame_count, record_writer, recording
    latest_photo = request.data
    frame_count += 1
    if recording and latest_photo:
        with record_lock:
            arr   = np.frombuffer(latest_photo, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                if record_writer is None:
                    h, w = frame.shape[:2]
                    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path = os.path.join(RECORDING_DIR, f"rec_{ts}.avi")
                    record_writer = cv2.VideoWriter(
                        path, cv2.VideoWriter_fourcc(*'XVID'), 15, (w, h))
                    add_event("recording", f"Gestartet: rec_{ts}.avi")
                record_writer.write(frame)
    return "OK", 200

@app.route('/stream')
def stream():
    def generate():
        while True:
            if latest_photo:
                if stream_quality < 100:
                    arr   = np.frombuffer(latest_photo, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        _, jpeg = cv2.imencode('.jpg', frame,
                                               [cv2.IMWRITE_JPEG_QUALITY, stream_quality])
                        data = jpeg.tobytes()
                    else:
                        data = latest_photo
                else:
                    data = latest_photo
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
            time.sleep(0.03)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({"motion": motion_detected})

@app.route('/stats')
def stats():
    uptime = int(time.time() - server_start_time)
    return jsonify({
        "uptime":           uptime,
        "frames":           frame_count,
        "motion_enabled":   motion_enabled,
        "auto_snapshot":    auto_snapshot,
        "recording":        recording,
        "sensitivity":      motion_sensitivity,
        "quality":          stream_quality,
    })

@app.route('/motion/toggle', methods=['POST'])
def motion_toggle():
    global motion_enabled, motion_detected
    motion_enabled  = not motion_enabled
    motion_detected = False if not motion_enabled else motion_detected
    add_event("config", f"Bewegung {'AN' if motion_enabled else 'AUS'}")
    return jsonify({"motion_enabled": motion_enabled})

@app.route('/sensitivity', methods=['POST'])
def set_sensitivity():
    global motion_sensitivity
    motion_sensitivity = int(request.get_json().get('value', 3000))
    return jsonify({"sensitivity": motion_sensitivity})

@app.route('/quality', methods=['POST'])
def set_quality():
    global stream_quality
    stream_quality = max(1, min(100, int(request.get_json().get('value', 80))))
    return jsonify({"quality": stream_quality})

@app.route('/auto_snapshot/toggle', methods=['POST'])
def auto_snapshot_toggle():
    global auto_snapshot
    auto_snapshot = not auto_snapshot
    add_event("config", f"Auto-Snap {'AN' if auto_snapshot else 'AUS'}")
    return jsonify({"auto_snapshot": auto_snapshot})

@app.route('/snapshot', methods=['POST'])
def manual_snapshot():
    if latest_photo:
        filename = save_snapshot(latest_photo, "manuell")
        return jsonify({"success": True, "filename": filename})
    return jsonify({"success": False})

@app.route('/record/toggle', methods=['POST'])
def record_toggle():
    global recording, record_writer
    with record_lock:
        recording = not recording
        if not recording and record_writer:
            record_writer.release()
            record_writer = None
            add_event("recording", "Gestoppt")
    return jsonify({"recording": recording})

@app.route('/snapshots')
def list_snapshots():
    files = sorted(os.listdir(SNAPSHOT_DIR), reverse=True)[:30]
    return jsonify({"snapshots": files})

@app.route('/snapshots/<path:filename>')
def get_snapshot(filename):
    return send_from_directory(SNAPSHOT_DIR, filename)

@app.route('/snapshots/<path:filename>', methods=['DELETE'])
def delete_snapshot(filename):
    path = os.path.join(SNAPSHOT_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        add_event("snapshot", f"Gelöscht: {filename}")
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route('/recordings')
def list_recordings():
    files = sorted(os.listdir(RECORDING_DIR), reverse=True)[:20]
    return jsonify({"recordings": files})

@app.route('/recordings/<path:filename>')
def get_recording(filename):
    return send_from_directory(RECORDING_DIR, filename)

@app.route('/events')
def get_events():
    return jsonify({"events": list(reversed(event_log[-50:]))})

@app.route('/events', methods=['DELETE'])
def clear_events():
    event_log.clear()
    return jsonify({"success": True})

@app.route('/')
def index():
    return render_template('index.html')

app.run(host='0.0.0.0', port=5151, threaded=True)
