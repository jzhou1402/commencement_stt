"""Database storage for graduates and transcripts. Uses Postgres if DATABASE_URL is set, otherwise SQLite."""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")


@contextmanager
def get_conn():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
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
                    transcript_path TEXT,
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
                    transcript_path TEXT,
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


def save_video(video_id, url, title, school, year, transcript_path):
    with get_conn() as conn:
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute(
                "INSERT INTO videos (id, url, title, school, year, transcript_path) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, school=EXCLUDED.school, year=EXCLUDED.year",
                (video_id, url, title, school, year, transcript_path),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO videos (id, url, title, school, year, transcript_path) VALUES (?, ?, ?, ?, ?, ?)",
                (video_id, url, title, school, year, transcript_path),
            )


def save_graduates(video_id, graduates, school, year):
    with get_conn() as conn:
        cur = conn.cursor()
        placeholder = "%s" if DATABASE_URL else "?"
        cur.execute(f"DELETE FROM graduates WHERE video_id = {placeholder}", (video_id,))
        for g in graduates:
            cur.execute(
                f"INSERT INTO graduates (video_id, name, degree, school, year) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                (video_id, g["name"], g.get("degree", "Unknown"), school, year),
            )


def get_all_graduates():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT g.name, g.degree, g.school, g.year, v.title as video_title "
            "FROM graduates g JOIN videos v ON g.video_id = v.id "
            "ORDER BY g.school, g.year, g.name"
        )
        rows = cur.fetchall()
        if DATABASE_URL:
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in rows]
        return [dict(r) for r in rows]


# Initialize on import
init_db()
