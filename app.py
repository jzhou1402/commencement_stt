#!/usr/bin/env python3
"""
Web UI for commencement pipeline. Run on port 3002.
"""

import os
import json
import hashlib
import re
import threading
from queue import Queue
from pathlib import Path

from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO
from db import save_video, save_graduates, get_cached_transcript, save_transcript, get_graduates_by_video
from costs import CostTracker

app = Flask(__name__)
app.config["SECRET_KEY"] = "commencement-stt"
socketio = SocketIO(app, cors_allowed_origins="*")

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# --- Job system ---
MAX_QUEUE_SIZE = 5
job_queue = Queue(maxsize=MAX_QUEUE_SIZE + 1)
queue_lock = threading.Lock()
active_job = None  # {"key": ..., "url": ..., "school": ..., "year": ..., "sids": set(), "cancel": Event}
cancelled_keys = set()


def url_key(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    if m:
        return m.group(1)
    return hashlib.sha256(url.encode()).hexdigest()[:16]


@socketio.on("connect")
def on_connect():
    pass


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    # Remove queued jobs for this socket
    with queue_lock:
        remaining = []
        while not job_queue.empty():
            remaining.append(job_queue.get_nowait())
        for job in remaining:
            job["sids"].discard(sid)
            if job["sids"]:
                job_queue.put(job)
            else:
                print(f"  Removed queued job {job['key']} (no listeners)", flush=True)
    # Remove from active job listeners (but don't cancel — it may finish for the DB)
    if active_job:
        active_job["sids"].discard(sid)


@socketio.on("reconnect_job")
def on_reconnect_job(data):
    """Client reconnected and wants to reattach to their job."""
    video_key = data.get("key")
    sid = request.sid
    if not video_key:
        return

    # Check if it's the active job
    if active_job and active_job["key"] == video_key:
        active_job["sids"].add(sid)
        socketio.emit("status", {"step": "metadata", "message": "Reconnected to active job..."}, to=sid)
        return

    # Check if it's queued
    with queue_lock:
        for i, job in enumerate(list(job_queue.queue)):
            if job["key"] == video_key:
                job["sids"].add(sid)
                socketio.emit("queue_position", {"position": i + 1, "total": job_queue.qsize()}, to=sid)
                return

    # Job finished while we were away — check DB for results
    graduates = get_graduates_by_video(video_key)
    if graduates:
        socketio.emit("metadata_complete", {
            "total_graduates": len(graduates),
            "groups": 0,
            "graduates": graduates,
        }, to=sid)
        socketio.emit("pipeline_complete", {"message": "Results loaded from database."}, to=sid)


@socketio.on("cancel_job")
def on_cancel_job(data):
    video_key = data.get("key")
    sid = request.sid
    if not video_key:
        return

    # Cancel active job
    if active_job and active_job["key"] == video_key:
        active_job["cancel"].set()
        socketio.emit("status", {"step": "cancel", "message": "Cancelling..."}, to=sid)
        return

    # Remove from queue
    with queue_lock:
        remaining = []
        while not job_queue.empty():
            remaining.append(job_queue.get_nowait())
        for job in remaining:
            if job["key"] != video_key:
                job_queue.put(job)
            else:
                print(f"  Cancelled queued job {video_key}", flush=True)

    socketio.emit("job_cancelled", {}, to=sid)
    _notify_queue_positions()


def _emit(event, data, job):
    """Emit to all listeners of a job."""
    for sid in list(job["sids"]):
        socketio.emit(event, data, to=sid)


def _check_cancel(job):
    """Raise if job was cancelled."""
    if job["cancel"].is_set():
        raise CancelledError()


class CancelledError(Exception):
    pass


def queue_worker():
    global active_job
    while True:
        job = job_queue.get()
        if not job["sids"]:
            print(f"  Skipping job {job['key']} (no listeners)", flush=True)
            job_queue.task_done()
            continue
        active_job = job
        _notify_queue_positions()
        try:
            run_pipeline(job)
        except CancelledError:
            _emit("job_cancelled", {}, job)
            print(f"  Job {job['key']} cancelled", flush=True)
        except Exception as e:
            _emit("error", {"message": str(e)}, job)
        finally:
            active_job = None
            job_queue.task_done()
            _notify_queue_positions()


def _notify_queue_positions():
    with queue_lock:
        items = list(job_queue.queue)
    for i, job in enumerate(items):
        _emit("queue_position", {"position": i + 1, "total": len(items)}, job)


worker_thread = threading.Thread(target=queue_worker, daemon=True)
worker_thread.start()


# --- YouTube download ---

def download_youtube_audio(url, job):
    import yt_dlp

    key = url_key(url)
    output_path = str(DOWNLOADS_DIR / f"{key}.%(ext)s")

    _emit("status", {"step": "download", "message": "Downloading audio from YouTube..."}, job)

    def progress_hook(d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "").strip()
            _emit("download_progress", {"message": f"Downloading... {pct}"}, job)
        elif d["status"] == "finished":
            _emit("download_progress", {"message": "Download complete, extracting audio..."}, job)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "source_address": "0.0.0.0",
        "cookiefile": str(Path(__file__).parent / "cookies.txt"),
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", key)

    audio_path = DOWNLOADS_DIR / f"{key}.mp3"
    if not audio_path.exists():
        for f in DOWNLOADS_DIR.glob(f"{key}.*"):
            if f.suffix != ".part":
                audio_path = f
                break

    _emit("status", {"step": "download", "message": f"Downloaded: {title}"}, job)
    return str(audio_path), title


# --- Audio processing ---

def get_audio_duration(filepath):
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def split_audio(filepath, chunk_seconds=600):
    import subprocess
    duration = get_audio_duration(filepath)
    base = Path(filepath)
    chunks = []
    start = 0
    i = 0
    while start < duration:
        chunk_path = base.parent / f"{base.stem}_chunk{i:03d}.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", filepath,
            "-ss", str(start), "-t", str(chunk_seconds),
            "-acodec", "libmp3lame", "-b:a", "64k", "-ac", "1",
            str(chunk_path),
        ], capture_output=True)
        if chunk_path.exists() and chunk_path.stat().st_size > 0:
            chunks.append((str(chunk_path), start))
        start += chunk_seconds
        i += 1
    return chunks, duration


# --- Transcription ---

def transcribe_audio(filepath, job, cost_tracker=None):
    from groq import Groq
    import time as _time

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not set")

    client = Groq(api_key=groq_key)

    _emit("status", {"step": "transcribe", "message": "Splitting audio into chunks..."}, job)
    chunks, duration = split_audio(filepath)

    if cost_tracker:
        cost_tracker.add_groq_audio(duration)
    print(f"  Split into {len(chunks)} chunks, duration={duration:.0f}s", flush=True)

    _emit("transcription_info", {"duration": duration, "language": "en"}, job)
    _emit("status", {"step": "transcribe", "message": f"Transcribing {len(chunks)} chunks via Groq..."}, job)

    all_segments = []
    full_text = []

    for i, (chunk_path, offset) in enumerate(chunks):
        _check_cancel(job)

        pct = round((i / len(chunks)) * 100, 1)
        _emit("transcription_progress", {
            "percent": pct, "current_time": round(offset, 1),
            "duration": round(duration, 1), "latest_text": f"Chunk {i+1}/{len(chunks)}..."
        }, job)
        print(f"  Transcribing chunk {i+1}/{len(chunks)} (offset={offset:.0f}s)...", flush=True)

        max_retries = 5
        for attempt in range(max_retries):
            try:
                with open(chunk_path, "rb") as f:
                    response = client.audio.transcriptions.create(
                        file=(Path(chunk_path).name, f.read()),
                        model="whisper-large-v3",
                        response_format="verbose_json",
                        language="en",
                    )
                break
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    wait_match = re.search(r"try again in (\d+)m?([\d.]+)?s", str(e))
                    if wait_match:
                        wait = int(wait_match.group(1)) * 60 + float(wait_match.group(2) or 0)
                    else:
                        wait = 30 * (attempt + 1)
                    wait = min(wait + 5, 300)
                    print(f"  Rate limited, waiting {wait:.0f}s (attempt {attempt+1}/{max_retries})...", flush=True)
                    _emit("transcription_progress", {
                        "percent": pct, "current_time": round(offset, 1),
                        "duration": round(duration, 1),
                        "latest_text": f"Rate limited, retrying in {int(wait)}s..."
                    }, job)
                    _time.sleep(wait)
                else:
                    raise
        else:
            raise Exception("Groq rate limit exceeded after max retries.")

        if hasattr(response, "segments") and response.segments:
            for seg in response.segments:
                seg_data = {
                    "start": seg.get("start", 0) + offset,
                    "end": seg.get("end", 0) + offset,
                    "text": seg.get("text", "").strip(),
                }
                if seg_data["text"]:
                    all_segments.append(seg_data)
                    full_text.append(seg_data["text"])

        Path(chunk_path).unlink(missing_ok=True)

        pct = round(((i + 1) / len(chunks)) * 100, 1)
        _emit("transcription_progress", {
            "percent": pct, "current_time": round(offset + 600, 1),
            "duration": round(duration, 1), "latest_text": full_text[-1] if full_text else ""
        }, job)
        print(f"  Chunk {i+1} done, {len(all_segments)} segments total", flush=True)

    return {
        "language": "en",
        "duration": duration,
        "segments": all_segments,
        "full_text": " ".join(full_text),
    }


# --- Pipeline ---

def run_pipeline(job):
    url = job["url"]
    school = job["school"]
    term = job.get("term", "")
    year = job["year"]
    key = job["key"]
    cost = CostTracker()

    # Check DB cache for transcript
    transcript_data = get_cached_transcript(key)
    if transcript_data:
        _emit("status", {"step": "transcribe", "message": "Found cached transcript..."}, job)
        _emit("transcription_progress", {"percent": 100, "current_time": transcript_data["duration"], "duration": transcript_data["duration"], "latest_text": "(cached)"}, job)
        _emit("transcription_complete", {"percent": 100, "total_segments": len(transcript_data["segments"]), "text_length": len(transcript_data["full_text"]), "cached": True}, job)
    else:
        _check_cancel(job)

        # Get audio: either from upload or YouTube download
        if "audio_path" in job:
            audio_path = job["audio_path"]
            title = job.get("filename", key)
            _emit("status", {"step": "transcribe", "message": f"Processing uploaded file: {title}"}, job)
        else:
            audio_path, title = download_youtube_audio(url, job)

        _check_cancel(job)
        transcript_data = transcribe_audio(audio_path, job, cost_tracker=cost)

        # Cache to DB
        save_transcript(key, url, title, transcript_data)

        _emit("transcription_complete", {"percent": 100, "total_segments": len(transcript_data["segments"]), "text_length": len(transcript_data["full_text"]), "cached": False}, job)

    _check_cancel(job)

    # Metadata extraction
    _emit("status", {"step": "metadata", "message": "Analyzing transcript for program boundaries..."}, job)

    from extract_metadata import extract_groups_chunked, convert_groups_to_graduates

    def on_chunk_progress(chunk_idx, total_chunks, groups_so_far, status_msg=None):
        if status_msg:
            _emit("status", {"step": "metadata", "message": status_msg}, job)
        pct = round((chunk_idx / total_chunks) * 100, 1) if total_chunks > 0 else 0
        grad_count = sum(len(g.get("names", [])) for g in groups_so_far)
        _emit("metadata_progress", {
            "percent": pct, "chunk": chunk_idx, "total_chunks": total_chunks,
            "groups_so_far": len(groups_so_far), "graduates_so_far": grad_count,
        }, job)

    groups = extract_groups_chunked(
        transcript_data, school, int(year), on_progress=on_chunk_progress, cost_tracker=cost
    )
    data = convert_groups_to_graduates(groups, school, int(year))
    graduates = data.get("graduates", [])

    # Persist to database
    save_video(key, url, "", school, int(year), term)
    save_graduates(key, graduates, school, int(year))

    _emit("metadata_complete", {
        "total_graduates": len(graduates),
        "groups": len(groups),
        "graduates": graduates,
    }, job)

    cost_summary = cost.summary()
    print(f"  Cost: ${cost_summary['total_cost']:.4f} (Groq: ${cost_summary['groq']['cost']:.4f}, OpenAI: ${cost_summary['openai']['cost']:.4f})", flush=True)
    _emit("pipeline_complete", {"message": "Pipeline complete!", "cost": cost_summary}, job)


# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    """Return current job state for refresh recovery."""
    active_key = active_job["key"] if active_job else None
    with queue_lock:
        queued = [{"key": j["key"], "url": j["url"]} for j in list(job_queue.queue)]
    return jsonify({"active_key": active_key, "queued": queued})


MAX_PER_IP = 5  # max queued videos per IP
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".mp4", ".mov", ".webm", ".ogg", ".aac", ".wma"}


def _get_ip():
    return request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr


def _check_queue_limits(ip, key, sid):
    """Check reattach, per-IP, and global queue limits. Returns (job_or_none, error_response_or_none)."""
    # If already active, reattach
    if active_job and active_job["key"] == key:
        active_job["sids"].add(sid)
        return None, jsonify({"status": "reattached", "position": 0})

    # If already queued, reattach
    with queue_lock:
        for job in list(job_queue.queue):
            if job["key"] == key:
                job["sids"].add(sid)
                return None, jsonify({"status": "reattached", "position": list(job_queue.queue).index(job) + 1})

    # Check per-IP limit
    with queue_lock:
        ip_count = sum(1 for j in list(job_queue.queue) if j.get("ip") == ip)
    if active_job and active_job.get("ip") == ip:
        ip_count += 1
    if ip_count >= MAX_PER_IP:
        return None, (jsonify({"error": f"You already have {ip_count} videos queued. Max {MAX_PER_IP} at a time."}), 429)

    # Check global queue capacity
    if job_queue.qsize() >= MAX_QUEUE_SIZE + 1:
        return None, (jsonify({"error": "Server is busy. Please try again in a few minutes."}), 429)

    return True, None


def _enqueue_job(job, sid):
    job_queue.put(job)
    position = job_queue.qsize()
    if position > 1 or active_job is not None:
        socketio.emit("queue_position", {"position": position, "total": position}, to=sid)
    return jsonify({"status": "queued", "key": job["key"], "position": position})


@app.route("/start", methods=["POST"])
def start():
    data = request.get_json()
    youtube_url = data.get("url", "").strip()
    school = data.get("school", "Unknown")
    term = data.get("term", "")
    year = data.get("year", "2025")
    sid = data.get("sid")
    ip = _get_ip()

    if not youtube_url:
        return jsonify({"error": "No YouTube URL provided"}), 400
    if "youtube.com" not in youtube_url and "youtu.be" not in youtube_url:
        return jsonify({"error": "Not a valid YouTube URL"}), 400

    key = url_key(youtube_url)

    ok, resp = _check_queue_limits(ip, key, sid)
    if resp:
        return resp

    job = {
        "key": key,
        "url": youtube_url,
        "school": school,
        "term": term,
        "year": year,
        "sids": {sid},
        "ip": ip,
        "cancel": threading.Event(),
    }
    return _enqueue_job(job, sid)


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400

    school = request.form.get("school", "Unknown")
    term = request.form.get("term", "")
    year = request.form.get("year", "2025")
    sid = request.form.get("sid")
    ip = _get_ip()

    # Read file and hash for dedup key
    file_data = file.read()
    key = hashlib.sha256(file_data).hexdigest()[:16]

    ok, resp = _check_queue_limits(ip, key, sid)
    if resp:
        return resp

    # Save file to downloads/
    audio_path = DOWNLOADS_DIR / f"{key}{ext}"
    audio_path.write_bytes(file_data)

    job = {
        "key": key,
        "audio_path": str(audio_path),
        "filename": file.filename,
        "url": f"upload://{file.filename}",
        "school": school,
        "term": term,
        "year": year,
        "sids": {sid},
        "ip": ip,
        "cancel": threading.Event(),
    }
    return _enqueue_job(job, sid)


@app.route("/queue")
def queue_status():
    """Return user's queued jobs. Accepts ?keys=key1,key2 to filter."""
    keys_param = request.args.get("keys", "")
    user_keys = set(k.strip() for k in keys_param.split(",") if k.strip())

    with queue_lock:
        if user_keys:
            jobs = [{"key": j["key"], "url": j["url"], "school": j["school"], "term": j.get("term", ""), "year": j["year"]} for j in list(job_queue.queue) if j["key"] in user_keys]
        else:
            jobs = [{"key": j["key"], "url": j["url"], "school": j["school"], "term": j.get("term", ""), "year": j["year"]} for j in list(job_queue.queue)]

    active = None
    if active_job and (not user_keys or active_job["key"] in user_keys):
        active = {"key": active_job["key"], "url": active_job["url"], "school": active_job["school"], "term": active_job.get("term", ""), "year": active_job["year"]}

    return jsonify({"active": active, "queued": jobs, "max": MAX_PER_IP})


@app.route("/datasets")
def datasets():
    """Return available datasets with preview."""
    from db import get_conn, _rows_to_dicts
    with get_conn() as conn:
        cur = conn.cursor()
        ph = "%s" if os.environ.get("DATABASE_URL") else "?"
        cur.execute(
            "SELECT v.id, v.title, v.school, v.year, v.term, COUNT(g.id) as grad_count "
            "FROM videos v JOIN graduates g ON v.id = g.video_id "
            "GROUP BY v.id, v.title, v.school, v.year, v.term "
            "HAVING COUNT(g.id) > 0 "
            "ORDER BY v.school, v.year"
        )
        vids = _rows_to_dicts(cur, cur.fetchall())

        for v in vids:
            cur.execute(
                f"SELECT name, degree FROM graduates WHERE video_id = {ph} ORDER BY id LIMIT 10",
                (v["id"],),
            )
            v["preview"] = _rows_to_dicts(cur, cur.fetchall())

    return jsonify(vids)


@app.route("/datasets/<video_id>/csv")
def dataset_csv(video_id):
    """Download full dataset as CSV."""
    from db import get_graduates_by_video
    graduates = get_graduates_by_video(video_id)
    if not graduates:
        return "Not found", 404

    import io
    output = io.StringIO()
    output.write("Name,Degree\n")
    for g in graduates:
        name = '"' + (g["name"] or "").replace('"', '""') + '"'
        degree = '"' + (g.get("degree") or "").replace('"', '""') + '"'
        output.write(f"{name},{degree}\n")

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={video_id}_graduates.csv"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
