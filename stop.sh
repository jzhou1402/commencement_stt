#!/bin/bash
# Stop the main app, switch to sleeping fallback
cd /Users/johnzhou/commencement_stt

# Kill the main app
lsof -ti:3002 | xargs kill -9 2>/dev/null
sleep 1

# Start the sleeping fallback + keep tunnel running
cloudflared tunnel --config /Users/johnzhou/.cloudflared/commencement-stt.yml run &
TUNNEL_PID=$!

.venv/bin/python sleeping.py &
APP_PID=$!

echo ""
echo "  commencement.stt is sleeping"
echo "  https://stt.johnzhou.xyz -> sleeping page + datasets"
echo ""

trap "kill $APP_PID $TUNNEL_PID 2>/dev/null" EXIT INT TERM
wait
