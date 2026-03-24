#!/usr/bin/env python3
"""
Run the full commencement pipeline: transcribe -> extract metadata -> enrich profiles.

Usage:
    python run_pipeline.py <audio_file> <school> <year> [--sample N]

Examples:
    python run_pipeline.py ceremony.mp3 MIT 2025
    python run_pipeline.py ceremony.mp3 MIT 2025 --sample 5
"""

import sys
import os
from pathlib import Path

from download_text import transcribe_audio
from extract_metadata import load_transcript, extract_groups_from_transcript, convert_groups_to_graduates

import json


def main():
    if len(sys.argv) < 4:
        print("Usage: python run_pipeline.py <audio_file> <school> <year> [--sample N]")
        sys.exit(1)

    audio_path = sys.argv[1]
    school = sys.argv[2]
    year = int(sys.argv[3])

    sample_size = None
    if "--sample" in sys.argv:
        idx = sys.argv.index("--sample")
        try:
            sample_size = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("Error: --sample requires a number")
            sys.exit(1)

    if not os.path.exists(audio_path):
        print(f"Error: File not found: {audio_path}")
        sys.exit(1)

    output_dir = Path(audio_path).parent
    base = Path(audio_path).stem

    # Step 1: Transcribe
    print("=" * 60)
    print("STEP 1: Transcription")
    print("=" * 60)
    transcribe_audio(audio_path)
    transcript_path = output_dir / f"{base}_transcript.txt"

    if not transcript_path.exists():
        print(f"Error: Expected transcript not found: {transcript_path}")
        sys.exit(1)

    # Step 2: Extract metadata
    print("\n" + "=" * 60)
    print("STEP 2: Metadata Extraction")
    print("=" * 60)
    transcript_text = load_transcript(str(transcript_path))
    groups = extract_groups_from_transcript(transcript_text, school, year)
    data = convert_groups_to_graduates(groups, school, year)

    graduates_filename = f"{school.lower()}_{year}_graduates.json"
    graduates_path = output_dir / graduates_filename
    with open(graduates_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    graduates = data["graduates"]
    print(f"Extracted {len(graduates)} graduates -> {graduates_path}")

    # Step 3: Enrich profiles (stubbed — not yet implemented)
    print("\n" + "=" * 60)
    print("STEP 3: Profile Enrichment (STUBBED)")
    print("=" * 60)
    print(f"Skipping enrichment. {len(graduates)} graduates ready for enrichment.")
    print(f"Run manually when ready: python enrich_profiles.py {graduates_path}")
    print(f"\nDone. Graduates saved to {graduates_path}")


if __name__ == "__main__":
    main()
