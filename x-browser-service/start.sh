#!/bin/sh
set -eu
Xvfb :99 -screen 0 1280x900x24 -nolisten tcp &
XVFB_PID=$!
trap 'kill "$XVFB_PID" 2>/dev/null || true' EXIT
sleep 1
openbox >/dev/null 2>&1 &
x11vnc -display :99 -localhost -rfbport 5900 -forever -shared -nopw -quiet >/dev/null 2>&1 &
exec python /app/server.py
