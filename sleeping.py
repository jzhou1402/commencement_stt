#!/usr/bin/env python3
"""
Lightweight fallback server for when the main app is sleeping.
Serves a quirky sleeping page + datasets API (from the database).
Runs on port 3002 when the main app isn't running.
"""

import os
from pathlib import Path
from flask import Flask, jsonify, Response

app = Flask(__name__)

SLEEPING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>commencement.stt</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Times New Roman', Times, serif;
            background: #fafaf8;
            color: #1a1a1a;
            min-height: 100vh;
            line-height: 1.6;
            display: flex;
            flex-direction: column;
        }
        .container { max-width: 680px; margin: 0 auto; padding: 60px 24px; flex: 1; }
        h1 { font-size: 32px; font-weight: 400; letter-spacing: -0.5px; margin-bottom: 4px; }
        .tagline { color: #666; font-size: 18px; font-style: italic; margin-bottom: 48px; }
        .section { border-top: 1px solid #ddd; padding: 32px 0; }
        h2 { font-size: 14px; font-weight: 400; text-transform: uppercase; letter-spacing: 1.5px; color: #999; margin-bottom: 20px; }
        .sleeping-msg {
            text-align: center;
            padding: 48px 0;
        }
        .sleeping-msg .moon { font-size: 64px; margin-bottom: 16px; }
        .sleeping-msg p { font-size: 18px; color: #666; margin-bottom: 8px; }
        .sleeping-msg .sub { font-size: 14px; color: #999; font-style: italic; }
        .dataset-card { border: 1px solid #eee; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
        .dataset-header { display: flex; justify-content: space-between; align-items: center; }
        .dataset-title { font-size: 16px; font-weight: 600; }
        .dataset-meta { font-size: 13px; color: #999; }
        .btn-download { padding: 8px 16px; font-family: 'Times New Roman', serif; font-size: 13px; background: #1a1a1a; color: #fafaf8; border: none; border-radius: 4px; cursor: pointer; }
        .btn-download:hover { background: #333; }
        footer { border-top: 1px solid #ddd; padding: 24px; text-align: center; font-size: 13px; color: #999; max-width: 680px; margin: 0 auto; width: 100%; }
    </style>
</head>
<body>
    <div class="container">
        <h1>commencement.stt</h1>
        <p class="tagline">Extract every graduate from a commencement ceremony.</p>

        <div class="sleeping-msg">
            <div class="moon">&#127769;</div>
            <p>The transcription service is currently sleeping.</p>
            <p class="sub">Come back during normal hours &mdash; the hamsters that power our servers need their rest.</p>
        </div>

        <div class="section" id="datasetsSection">
            <h2>Datasets</h2>
            <div id="datasetsList"><p style="color:#999; font-size:14px;">Loading datasets...</p></div>
        </div>
    </div>
    <footer>commencement.stt</footer>

    <script>
        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        fetch('/datasets').then(r => r.json()).then(datasets => {
            const container = document.getElementById('datasetsList');
            if (!datasets.length) {
                container.innerHTML = '<p style="color:#999; font-size:14px;">No datasets yet.</p>';
                return;
            }
            container.innerHTML = datasets.map(d => `
                <div class="dataset-card">
                    <div class="dataset-header">
                        <div>
                            <div class="dataset-title">${escapeHtml(d.school)} ${d.term ? escapeHtml(d.term) + ' ' : ''}${d.year}</div>
                            <div class="dataset-meta">${d.grad_count} graduates</div>
                        </div>
                        <a href="/datasets/${encodeURIComponent(d.id)}/csv" class="btn-download">Download CSV</a>
                    </div>
                </div>
            `).join('');
        }).catch(() => {
            document.getElementById('datasetsList').innerHTML = '<p style="color:#999; font-size:14px;">Could not load datasets.</p>';
        });
    </script>
</body>
</html>"""


@app.route("/")
def index():
    return SLEEPING_HTML


@app.route("/datasets")
def datasets():
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
    return jsonify(vids)


@app.route("/datasets/<video_id>/csv")
def dataset_csv(video_id):
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
    app.run(host="0.0.0.0", port=3002)
