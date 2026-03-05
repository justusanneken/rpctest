from picamera2 import Picamera2  
import requests                  
import time                      
import cv2                       

# Server IP
SERVER_URL = "http://10.0.0.8:5050/upload"

# Camera Einstellen
camera = Picamera2()
camera.configure(camera.create_preview_configuration())
camera.start()

print("Stream gestartet!")

while True:
    # Foto machen
    frame = camera.capture_array()

    # da die Kamera auch IR aufnimmt also 4ch hat, wird der nicht benötigte kanal gedroppt.
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    # da die Kamera auch IR aufnimmt werden die Farben Rot und Blau gewechselt um ein natürlicheres bild auszugeben
    b, g, r = cv2.split(frame)
    frame = cv2.merge([r, g, b])

    # Bild um 180 Grad drehen
    frame = cv2.rotate(frame, cv2.ROTATE_180)

    # Foto convertierung zu jpeg
    success, jpeg = cv2.imencode('.jpg', frame)

    if not success:
        print("Frame konnte nicht konvertiert werden...")
        time.sleep(1)
        continue

    # Foto zum server schicken
    try:
        requests.post(SERVER_URL, data=jpeg.tobytes(), headers={"Content-Type": "image/jpeg"}, timeout=2)
    except:
        print("Couldn't reach server, trying again...")
        time.sleep(1)
