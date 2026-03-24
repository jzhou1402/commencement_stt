#!/usr/bin/env python3
"""
Web UI for commencement pipeline. Run on port 3002.

Usage:
    python app.py
"""

import os
import json
import hashlib
import threading
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from db import save_video, save_graduates

app = Flask(__name__)
app.config["SECRET_KEY"] = "commencement-stt"
socketio = SocketIO(app, cors_allowed_origins="*")

DOWNLOADS_DIR = Path("downloads")
CACHE_DIR = Path("cache")
DOWNLOADS_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

CACHE_INDEX_PATH = CACHE_DIR / "transcripts.json"


def load_cache():
    if CACHE_INDEX_PATH.exists():
        with open(CACHE_INDEX_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_INDEX_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def url_key(url):
    """Stable cache key from a YouTube URL (normalize to video ID if possible)."""
    import re
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    if m:
        return m.group(1)
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def download_youtube_audio(url, sid):
    """Download audio from YouTube URL via yt-dlp. Returns path to audio file."""
    import yt_dlp

    key = url_key(url)
    output_path = str(DOWNLOADS_DIR / f"{key}.%(ext)s")

    socketio.emit("status", {"step": "download", "message": "Downloading audio from YouTube..."}, to=sid)

    def progress_hook(d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "").strip()
            socketio.emit("download_progress", {"message": f"Downloading... {pct}"}, to=sid)
        elif d["status"] == "finished":
            socketio.emit("download_progress", {"message": "Download complete, extracting audio..."}, to=sid)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", key)

    audio_path = DOWNLOADS_DIR / f"{key}.mp3"
    if not audio_path.exists():
        # yt-dlp may have used a different extension
        for f in DOWNLOADS_DIR.glob(f"{key}.*"):
            if f.suffix != ".part":
                audio_path = f
                break

    socketio.emit("status", {"step": "download", "message": f"Downloaded: {title}"}, to=sid)
    return str(audio_path), title


def get_audio_duration(filepath):
    """Get duration in seconds via ffprobe."""
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def split_audio(filepath, chunk_seconds=600):
    """Split audio into chunks using ffmpeg. Returns list of chunk file paths."""
    import subprocess
    duration = get_audio_duration(filepath)
    base = Path(filepath)
    chunks = []
    start = 0
    i = 0

    while start < duration:
        chunk_path = base.parent / f"{base.stem}_chunk{i:03d}.mp3"
        cmd = [
            "ffmpeg", "-y", "-i", filepath,
            "-ss", str(start), "-t", str(chunk_seconds),
            "-acodec", "libmp3lame", "-b:a", "64k", "-ac", "1",  # mono 64k to stay under 25MB
            str(chunk_path),
        ]
        subprocess.run(cmd, capture_output=True)
        if chunk_path.exists() and chunk_path.stat().st_size > 0:
            chunks.append((str(chunk_path), start))
        start += chunk_seconds
        i += 1

    return chunks, duration


def transcribe_audio(filepath, sid):
    """Transcribe audio using Groq Whisper API, splitting into chunks for long files."""
    from groq import Groq

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not set")

    client = Groq(api_key=groq_key)

    socketio.emit("status", {"step": "transcribe", "message": "Splitting audio into chunks..."}, to=sid)
    chunks, duration = split_audio(filepath)
    print(f"  Split into {len(chunks)} chunks, duration={duration:.0f}s", flush=True)

    socketio.emit("transcription_info", {"duration": duration, "language": "en"}, to=sid)
    socketio.emit("status", {"step": "transcribe", "message": f"Transcribing {len(chunks)} chunks via Groq..."}, to=sid)

    all_segments = []
    full_text = []

    for i, (chunk_path, offset) in enumerate(chunks):
        pct = round(((i) / len(chunks)) * 100, 1)
        socketio.emit(
            "transcription_progress",
            {"percent": pct, "current_time": round(offset, 1), "duration": round(duration, 1), "latest_text": f"Chunk {i+1}/{len(chunks)}..."},
            to=sid,
        )
        print(f"  Transcribing chunk {i+1}/{len(chunks)} (offset={offset:.0f}s)...", flush=True)

        with open(chunk_path, "rb") as f:
            response = client.audio.transcriptions.create(
                file=(Path(chunk_path).name, f.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="en",
            )

        # Process segments with offset adjustment
        if hasattr(response, "segments") and response.segments:
            for seg in response.segments:
                seg_data = {
                    "start": seg.get("start", seg.get("start", 0)) + offset,
                    "end": seg.get("end", seg.get("end", 0)) + offset,
                    "text": seg.get("text", "").strip(),
                }
                if seg_data["text"]:
                    all_segments.append(seg_data)
                    full_text.append(seg_data["text"])

        # Clean up chunk file
        Path(chunk_path).unlink(missing_ok=True)

        pct = round(((i + 1) / len(chunks)) * 100, 1)
        latest = full_text[-1] if full_text else ""
        socketio.emit(
            "transcription_progress",
            {"percent": pct, "current_time": round(offset + 600, 1), "duration": round(duration, 1), "latest_text": latest},
            to=sid,
        )
        print(f"  Chunk {i+1} done, {len(all_segments)} segments total", flush=True)

    transcript_text = " ".join(full_text)

    return {
        "language": "en",
        "duration": duration,
        "segments": all_segments,
        "full_text": transcript_text,
    }


def run_pipeline(youtube_url, school, year, sid):
    """Download YouTube audio, transcribe (or load cache), extract metadata."""
    try:
        key = url_key(youtube_url)
        cache = load_cache()

        # Check cache
        if key in cache:
            socketio.emit("status", {"step": "transcribe", "message": "Found cached transcript, skipping transcription..."}, to=sid)
            cached = cache[key]
            transcript_path = cached["transcript_path"]
            with open(transcript_path) as f:
                transcript_data = json.load(f)
            transcript_text = transcript_data["full_text"]

            socketio.emit("transcription_progress", {"percent": 100, "current_time": transcript_data["duration"], "duration": transcript_data["duration"], "latest_text": "(cached)"}, to=sid)
            socketio.emit("transcription_complete", {"percent": 100, "total_segments": len(transcript_data["segments"]), "text_length": len(transcript_text), "cached": True}, to=sid)
        else:
            # Download
            audio_path, title = download_youtube_audio(youtube_url, sid)

            # Transcribe
            transcript_data = transcribe_audio(audio_path, sid)
            transcript_text = transcript_data["full_text"]

            # Save transcript
            transcript_path = str(CACHE_DIR / f"{key}_transcript.json")
            with open(transcript_path, "w", encoding="utf-8") as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)

            # Update cache
            cache[key] = {
                "url": youtube_url,
                "title": title,
                "transcript_path": transcript_path,
            }
            save_cache(cache)

            socketio.emit("transcription_complete", {"percent": 100, "total_segments": len(transcript_data["segments"]), "text_length": len(transcript_text), "cached": False}, to=sid)

        # Step 2: Metadata extraction (smart program-boundary chunking)
        socketio.emit("status", {"step": "metadata", "message": "Analyzing transcript for program boundaries..."}, to=sid)

        from extract_metadata import extract_groups_chunked, convert_groups_to_graduates

        def on_chunk_progress(chunk_idx, total_chunks, groups_so_far, status_msg=None):
            if status_msg:
                socketio.emit("status", {"step": "metadata", "message": status_msg}, to=sid)
            if total_chunks > 0:
                pct = round((chunk_idx / total_chunks) * 100, 1)
            else:
                pct = 0
            grad_count = sum(len(g.get("names", [])) for g in groups_so_far)
            socketio.emit(
                "metadata_progress",
                {
                    "percent": pct,
                    "chunk": chunk_idx,
                    "total_chunks": total_chunks,
                    "groups_so_far": len(groups_so_far),
                    "graduates_so_far": grad_count,
                },
                to=sid,
            )

        groups = extract_groups_chunked(
            transcript_data, school, int(year), on_progress=on_chunk_progress
        )
        data = convert_groups_to_graduates(groups, school, int(year))
        graduates = data.get("graduates", [])

        graduates_filename = f"{school.lower()}_{year}_graduates.json"
        graduates_path = CACHE_DIR / graduates_filename
        with open(graduates_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Persist to database
        video_title = load_cache().get(key, {}).get("title", youtube_url)
        save_video(key, youtube_url, video_title, school, int(year), str(graduates_path))
        save_graduates(key, graduates, school, int(year))

        socketio.emit(
            "metadata_complete",
            {
                "total_graduates": len(graduates),
                "groups": len(groups),
                "graduates": graduates,
                "file": str(graduates_path),
            },
            to=sid,
        )

        socketio.emit("pipeline_complete", {"message": "Pipeline complete!", "graduates_file": str(graduates_path)}, to=sid)

    except Exception as e:
        socketio.emit("error", {"message": str(e)}, to=sid)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start():
    data = request.get_json()
    youtube_url = data.get("url", "").strip()
    school = data.get("school", "Unknown")
    year = data.get("year", "2025")
    sid = data.get("sid")

    if not youtube_url:
        return jsonify({"error": "No YouTube URL provided"}), 400

    # Quick check that it looks like a YouTube URL
    if "youtube.com" not in youtube_url and "youtu.be" not in youtube_url:
        return jsonify({"error": "Not a valid YouTube URL"}), 400

    key = url_key(youtube_url)
    cache = load_cache()
    cached = key in cache

    thread = threading.Thread(target=run_pipeline, args=(youtube_url, school, year, sid))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started", "cached": cached})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
