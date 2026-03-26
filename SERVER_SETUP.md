# Server Setup Guide (Windows)

How to get commencement.stt running on a new Windows machine.

## 1. Install dependencies

- **Python 3.10+**: https://python.org/downloads
- **ffmpeg**: `winget install ffmpeg` or download from https://ffmpeg.org
- **cloudflared**: `winget install Cloudflare.cloudflared` or download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
- **Git**: https://git-scm.com

## 2. Clone and install

```powershell
git clone https://github.com/jzhou1402/commencement_stt.git
cd commencement_stt
pip install -r requirements.txt
```

## 3. Copy files from old machine

These are gitignored — copy manually (USB, SCP, etc.):

```
commencement.db                    → commencement_stt\commencement.db
```

From the old Mac, also grab the Cloudflare tunnel credentials:

```
~/.cloudflared/config.yml
~/.cloudflared/3a8055b1-7d3c-49c4-9cc0-24a7bad3e149.json
```

Put them in `C:\Users\<you>\.cloudflared\`

## 4. Create start script

Create `start.bat` in the repo folder:

```bat
@echo off
set GROQ_API_KEY=your-groq-key
set OPENAI_API_KEY=your-openai-key
python app.py
```

## 5. Fix Cloudflare config paths

Edit `C:\Users\<you>\.cloudflared\config.yml`:

```yaml
tunnel: 3a8055b1-7d3c-49c4-9cc0-24a7bad3e149
credentials-file: C:\Users\<you>\.cloudflared\3a8055b1-7d3c-49c4-9cc0-24a7bad3e149.json

ingress:
  - hostname: johnzhou.xyz
    service: http://localhost:3002
  - hostname: api.johnzhou.xyz
    service: http://localhost:3002
  - service: http_status:404
```

## 6. Test locally

```powershell
# Terminal 1: start the app
start.bat
# Visit http://localhost:3002

# Terminal 2: start the tunnel
cloudflared tunnel run commencement
# Visit https://johnzhou.xyz
```

## 7. Run on startup (Windows Service)

### App — use Task Scheduler

1. Open **Task Scheduler** → Create Task
2. **General**: Name: `commencement-stt`, check "Run whether user is logged on or not"
3. **Triggers**: At startup
4. **Actions**: Start a program
   - Program: `C:\path\to\commencement_stt\start.bat`
   - Start in: `C:\path\to\commencement_stt`
5. **Settings**: Check "Restart the task if it fails", every 1 minute, up to 999 times

### Tunnel — install as Windows service

```powershell
cloudflared service install
```

This auto-registers as a Windows service that starts on boot. If it doesn't pick up the config, copy it:

```powershell
copy C:\Users\<you>\.cloudflared\config.yml C:\Windows\System32\config\systemprofile\.cloudflared\config.yml
copy C:\Users\<you>\.cloudflared\3a8055b1-7d3c-49c4-9cc0-24a7bad3e149.json C:\Windows\System32\config\systemprofile\.cloudflared\
```

Then restart the service:

```powershell
net stop cloudflared
net start cloudflared
```

## 8. Verify

```powershell
# App running?
curl http://localhost:3002/

# Tunnel connected?
cloudflared tunnel info commencement

# Site live?
curl https://johnzhou.xyz/
```

## Restarting

```powershell
# Restart tunnel
net stop cloudflared && net start cloudflared

# Restart app — kill and relaunch start.bat, or restart via Task Scheduler
```

## Logs

- App: check the terminal running start.bat, or redirect in the bat file:
  ```bat
  python app.py >> logs\stdout.log 2>> logs\stderr.log
  ```
- Tunnel: `C:\Windows\System32\config\systemprofile\.cloudflared\cloudflared.log`
