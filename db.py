"""Database storage for graduates and transcripts. Uses Postgres if DATABASE_URL is set, otherwise SQLite."""

import os
import json
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")


def _ph(n=1):
    """Return n placeholder(s) for the current DB."""
    p = "%s" if DATABASE_URL else "?"
    return ", ".join([p] * n)


@contextmanager
def get_conn():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        conn = sqlite3.connect("commencement.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _rows_to_dicts(cur, rows):
    if DATABASE_URL:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    return [dict(r) for r in rows]


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT,
                    school TEXT,
                    year INTEGER,
                    transcript TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS graduates (
                    id SERIAL PRIMARY KEY,
                    video_id TEXT NOT NULL REFERENCES videos(id),
                    name TEXT NOT NULL,
                    degree TEXT,
                    school TEXT,
                    year INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_graduates_video ON graduates(video_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_graduates_name ON graduates(name)")
        else:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT,
                    school TEXT,
                    year INTEGER,
                    transcript TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS graduates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL REFERENCES videos(id),
                    name TEXT NOT NULL,
                    degree TEXT,
                    school TEXT,
                    year INTEGER,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_graduates_video ON graduates(video_id);
                CREATE INDEX IF NOT EXISTS idx_graduates_name ON graduates(name);
            """)


# --- Transcript cache ---

def get_cached_transcript(video_id):
    """Return transcript data dict if cached, else None."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT transcript, title FROM videos WHERE id = {_ph()}", (video_id,))
        row = cur.fetchone()
        if row:
            transcript = row[0] if DATABASE_URL else row["transcript"]
            if transcript:
                return json.loads(transcript)
    return None


def save_transcript(video_id, url, title, transcript_data):
    """Cache a transcript in the DB."""
    transcript_json = json.dumps(transcript_data)
    with get_conn() as conn:
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute(
                "INSERT INTO videos (id, url, title, transcript) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, transcript=EXCLUDED.transcript",
                (video_id, url, title, transcript_json),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO videos (id, url, title, transcript) VALUES (?, ?, ?, ?)",
                (video_id, url, title, transcript_json),
            )


# --- Videos ---

def save_video(video_id, url, title, school, year):
    with get_conn() as conn:
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute(
                "INSERT INTO videos (id, url, title, school, year) VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, school=EXCLUDED.school, year=EXCLUDED.year",
                (video_id, url, title, school, year),
            )
        else:
            cur.execute(
                f"UPDATE videos SET school = {_ph()}, year = {_ph()} WHERE id = {_ph()}",
                (school, year, video_id),
            )
            if cur.rowcount == 0:
                cur.execute(
                    f"INSERT INTO videos (id, url, title, school, year) VALUES ({_ph(5)})",
                    (video_id, url, title, school, year),
                )


# --- Graduates ---

def save_graduates(video_id, graduates, school, year):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM graduates WHERE video_id = {_ph()}", (video_id,))
        for g in graduates:
            cur.execute(
                f"INSERT INTO graduates (video_id, name, degree, school, year) VALUES ({_ph(5)})",
                (video_id, g["name"], g.get("degree", "Unknown"), school, year),
            )


def get_graduates_by_video(video_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT name, degree, school, year FROM graduates WHERE video_id = {_ph()} ORDER BY id", (video_id,))
        return _rows_to_dicts(cur, cur.fetchall())


# Initialize on import
init_db()
