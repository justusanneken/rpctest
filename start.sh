#!/bin/bash

echo "Installiere server dependencies..."
pip install flask opencv-python

echo ""
echo "Starte server: http://localhost:5050"
echo ""

python server/stream_server.py
