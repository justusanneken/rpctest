PI KAMERA STREAM - WIE ES FUNKTIONIERT
=======================================

TL;DR
-----
Pi filmt → schickt Bilder ans Netzwerk → Server zeigt sie im Browser an.
Bei Bewegung erscheint ein roter Alarm auf der Webseite.

Server starten:  bash start.sh
Pi starten:      python3 pi_client/stream_client.py
Im Browser:      http://10.0.0.8:5050

-----

ÜBERSICHT
---------
Der Raspberry Pi nimmt Videoframes auf und sendet sie über das Netzwerk an
einen Server. Der Server zeigt den Stream auf einer Webseite an und erkennt
Bewegungen.


DATEIEN
-------

pi_client/stream_client.py
  Läuft auf dem Raspberry Pi.
  - Öffnet die CSI-Kamera mit picamera2
  - Wendet eine Farbkorrektur für die NoIR-Kamera an (kein IR-Filter = Rosa-Stich)
  - Wandelt jeden Frame in ein JPEG-Bild um, damit die Dateigröße klein bleibt
  - Sendet das JPEG per HTTP POST-Anfrage an den Server
  - Falls der Server nicht erreichbar ist, wartet er 1 Sekunde und versucht es erneut

server/stream_server.py
  Läuft auf dem Windows-PC oder Mac, der als Server dient.
  - Empfängt eingehende Fotos vom Pi unter der Adresse /upload
  - Speichert das neueste Foto im Arbeitsspeicher
  - Führt einen Hintergrund-Thread aus, der jeden neuen Frame mit dem vorherigen
    vergleicht, um Bewegungen zu erkennen (wenn genug Pixel sich verändert haben,
    wird Bewegung gemeldet)
  - Stellt den Livestream für den Browser unter /stream bereit
  - Stellt die Webseite unter / bereit
  - Teilt der Webseite unter /status mit, ob Bewegung erkannt wurde

server/templates/index.html
  Die Webseite, die im Browser angezeigt wird.
  - Zeigt den Livestream als kontinuierlich aktualisiertes Bild an
  - Fragt den Server jede Sekunde, ob Bewegung erkannt wurde
  - Bei Bewegung wird oben ein roter "Bewegung erkannt!!"-Kasten angezeigt
  - Ohne Bewegung ist der Kasten ausgeblendet

start.sh
  Auf dem Server-Rechner ausführen (Mac oder Windows mit Git Bash).
  - Installiert die benötigten Python-Pakete (flask, opencv-python)
  - Startet den Server


AUSFÜHREN
---------

1. Auf dem SERVER-Rechner:
   bash start.sh
   Dann im Browser http://localhost:5050 öffnen.

2. Auf dem RASPBERRY PI:
   git clone https://github.com/justusanneken/rpc.git
   cd rpc
   sudo apt install python3-picamera2 python3-opencv python3-requests -y
   python3 pi_client/stream_client.py

   Der Pi sendet dann automatisch Frames an 10.0.0.8:5050.


BEWEGUNGSERKENNUNG - WIE ES FUNKTIONIERT
-----------------------------------------
1. Jeder eingehende Frame wird in Graustufen umgewandelt und leicht weichgezeichnet
2. Er wird Pixel für Pixel mit dem vorherigen Frame verglichen
3. Pixel, die sich stark verändert haben, werden gezählt
4. Wenn mehr als 3000 Pixel sich verändert haben, wird Bewegung gemeldet
5. Die Webseite prüft /status jede Sekunde und zeigt den Alarm bei Bedarf an
