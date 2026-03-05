#Server

from flask import Flask, Response, render_template, request, jsonify
import time
import cv2
import numpy as np
import threading

app = Flask(__name__)

# Variablen
latest_photo = None
motion_detected = False
previous_frame = None

# Bewegungserkennung
def detection_loop():
    global motion_detected, previous_frame
    while True:
        frame_data = latest_photo
        if frame_data:
            image_data = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            if frame is not None:
                # Schwarzweißkonvertierung, Blur
                grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                grey = cv2.GaussianBlur(grey, (21, 21), 0)

                if previous_frame is None:
                    previous_frame = grey
                else:
                    # Vorherigen mit dem aktuellen frame vergleichen
                    diff = cv2.absdiff(previous_frame, grey)
                    # Große änderungen= weiß rest schwarz
                    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                    # Pxel anzahl zählen
                    changed_pixels = cv2.countNonZero(thresh)
                    # wenn genug änderung frame =grau
                    motion_detected = changed_pixels > 3000
                    previous_frame = grey
        time.sleep(0.2)

# Start erkennung
threading.Thread(target=detection_loop, daemon=True).start()

# empfange foto von pi
@app.route('/upload', methods=['POST'])
def upload():
    global latest_photo
    latest_photo = request.data
    return "OK", 200

# bewegungserkennungsübermitllung
@app.route('/status')
def status():
    return jsonify({"motion": motion_detected})

# livestream vom browser aufgerufen
@app.route('/stream')
def stream():
    def generate():
        while True:
            if latest_photo:
                # fotos werden so gesendet wie ein stream
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + latest_photo + b'\r\n')
            # warte um fps einzuhalten
            time.sleep(0.03)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# website
@app.route('/')
def index():
    return render_template('index.html')

# Starte Server
app.run(host='0.0.0.0', port=5050, threaded=True)
