#!/bin/bash
# Start commencement-stt server + Cloudflare tunnel
cd /Users/johnzhou/commencement_stt

# Kill any existing instances on port 3002
lsof -ti:3002 | xargs kill -9 2>/dev/null
sleep 1

# Start the tunnel in background
cloudflared tunnel --config /Users/johnzhou/.cloudflared/commencement-stt.yml run &
TUNNEL_PID=$!

# Start the Flask app (loads .env.local via dotenv)
.venv/bin/python app.py &
APP_PID=$!

echo ""
echo "  commencement.stt is live"
echo "  Local:  http://localhost:3002"
echo "  Public: https://stt.johnzhou.xyz"
echo ""
echo "  Stop with: bash stop.sh"
echo ""

# Clean up both on exit
trap "kill $APP_PID $TUNNEL_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
