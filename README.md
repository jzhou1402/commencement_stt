# commencement.stt

Extract every graduate from a commencement ceremony video.

Paste a YouTube link, get a structured list of graduates and their degree programs.

## Architecture

```
Browser (johnzhou.xyz)
    |
Cloudflare Tunnel
    |
Your Mac running app.py on port 3002
    |
    +-- yt-dlp: downloads YouTube audio
    +-- Groq Whisper API: transcribes audio
    +-- OpenAI GPT-4o: extracts graduates + degree programs
    +-- SQLite: caches transcripts + stores results
```

## Local setup

### 1. Install dependencies

```bash
brew install ffmpeg
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
export GROQ_API_KEY="your-groq-key"
export OPENAI_API_KEY="your-openai-key"
```

### 3. Run the server

```bash
python app.py
```

Server starts on http://localhost:3002.

### 4. (Optional) Expose via Cloudflare Tunnel

```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create commencement
cloudflared tunnel route dns commencement yourdomain.com
cloudflared tunnel run commencement
```

## Persistent services (macOS)

To keep the server and tunnel running after reboot:

**App server** — create a launch agent at `~/Library/LaunchAgents/com.commencement.stt.plist` pointing to a `start.sh` script that sets env vars and runs `python app.py`.

**Cloudflare Tunnel** — `sudo cloudflared service install`, then copy your `config.yml` and credentials JSON to `/etc/cloudflared/`.

## How it works

1. **Download** — yt-dlp grabs the audio from YouTube
2. **Transcribe** — Audio is split into 10-min chunks, sent to Groq's Whisper API with rate limit retry
3. **Find boundaries** — GPT-4o scans the transcript for program/department announcements
4. **Extract names** — Each program section is sent to GPT-4o to pull out graduate names and their specific degree
5. **Store** — Results saved to SQLite (graduates table + transcript cache)

Transcripts are cached by YouTube video ID so re-processing the same video skips transcription.

## Features

- Real-time progress via WebSocket
- Job queue (1 active, max 5 waiting)
- Refresh-resistant (reconnects to active jobs)
- Cancel button
- CSV download
- Cost tracking (Groq audio + OpenAI tokens)
- Transcript caching in DB

## Cost per ceremony

| Step | Cost |
|------|------|
| Transcription (Groq) | ~$0.003/min of audio |
| Boundary detection (GPT-4o) | ~$0.01-0.05 |
| Name extraction (GPT-4o) | ~$0.05-0.15 |
| **Typical 2hr ceremony** | **~$0.50-1.00** |

## License

MIT
