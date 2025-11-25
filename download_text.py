#!/usr/bin/env python3
"""
STEP 1: Speech-to-Text transcription using Whisper Large V3

This script ONLY does transcription. For name extraction and enrichment:
- Step 2: Run extract_metadata.py to get structured graduate data
- Step 3: Run enrich_profiles.py to research each graduate online

Supports: MP3, WAV, FLAC, M4A, OGG, MP4, MOV, AVI, etc.
Recommended: Use MP3 or WAV for smaller file sizes and faster processing
"""

import os
import json
from pathlib import Path
from datetime import timedelta
from faster_whisper import WhisperModel


def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS.mmm format"""
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    secs = td.seconds % 60
    millis = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def transcribe_audio(
    audio_path,
    model_size="large-v3",
    device="auto",
    compute_type="auto",
    language="en",
    output_format="all"
):
    """
    Transcribe audio/video using Whisper model
    
    Args:
        audio_path: Path to audio/video file (mp3, wav, flac, mp4, mov, etc.)
        model_size: Model size - "large-v3" (best), "large-v2", "medium", "small", "base", "tiny"
        device: "cuda" for GPU, "cpu" for CPU, "auto" to detect automatically
        compute_type: "auto" (recommended), "float16" (GPU), "int8" (CPU), "float32"
        language: Language code (e.g., "en", "es", "zh")
        output_format: "txt", "json", "srt", "vtt", or "all"
    
    Returns:
        Dictionary with transcription results
    """
    
    # Auto-detect best compute type based on available hardware
    if compute_type == "auto":
        import torch
        if torch.cuda.is_available():
            compute_type = "float16"
            if device == "auto":
                device = "cuda"
        else:
            # CPU - use int8 for best performance
            compute_type = "int8"
            if device == "auto":
                device = "cpu"
    
    print(f"Loading Whisper model: {model_size}")
    print(f"Device: {device}, Compute type: {compute_type}")
    
    # Initialize model
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root=None  # Uses default cache
    )
    
    print(f"\nTranscribing audio: {audio_path}")
    print("This may take a few minutes depending on audio length...\n")
    
    # Transcribe with word-level timestamps (helps with name recognition)
    segments, info = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,  # Voice Activity Detection - filters out silence
        vad_parameters=dict(
            min_silence_duration_ms=500  # Adjust for better name detection
        ),
        beam_size=5,  # Higher beam size = better accuracy (but slower)
        best_of=5,    # Number of candidates to consider
        temperature=0.0  # Use greedy decoding for consistency
    )
    
    print(f"Detected language: {info.language} (probability: {info.language_probability:.2%})")
    print(f"Duration: {info.duration:.2f} seconds\n")
    
    # Collect results
    results = {
        "language": info.language,
        "duration": info.duration,
        "segments": []
    }
    
    full_text = []
    
    print("Transcription Results:")
    print("=" * 80)
    
    for segment in segments:
        segment_data = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        }
        
        # Add word-level timestamps (useful for identifying names)
        if segment.words:
            segment_data["words"] = [
                {
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                    "probability": word.probability
                }
                for word in segment.words
            ]
        
        results["segments"].append(segment_data)
        full_text.append(segment.text.strip())
        
        # Print with timestamp
        start_time = format_timestamp(segment.start)
        end_time = format_timestamp(segment.end)
        print(f"[{start_time} --> {end_time}]")
        print(f"{segment.text.strip()}\n")
    
    results["full_text"] = " ".join(full_text)
    
    # Save outputs
    base_path = Path(audio_path).stem
    output_dir = Path(audio_path).parent
    
    if output_format in ["txt", "all"]:
        txt_path = output_dir / f"{base_path}_transcript.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(results["full_text"])
        print(f"\n✓ Saved plain text to: {txt_path}")
    
    if output_format in ["json", "all"]:
        json_path = output_dir / f"{base_path}_transcript.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved detailed JSON to: {json_path}")
    
    if output_format in ["srt", "all"]:
        srt_path = output_dir / f"{base_path}_transcript.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(results["segments"], 1):
                start = format_timestamp(seg["start"]).replace(".", ",")
                end = format_timestamp(seg["end"]).replace(".", ",")
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{seg['text']}\n\n")
        print(f"✓ Saved SRT subtitles to: {srt_path}")
    
    if output_format in ["vtt", "all"]:
        vtt_path = output_dir / f"{base_path}_transcript.vtt"
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for seg in results["segments"]:
                start = format_timestamp(seg["start"])
                end = format_timestamp(seg["end"])
                f.write(f"{start} --> {end}\n")
                f.write(f"{seg['text']}\n\n")
        print(f"✓ Saved VTT subtitles to: {vtt_path}")
    
    print("\n" + "=" * 80)
    print(f"Transcription complete! Total segments: {len(results['segments'])}")
    
    return results


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("STEP 1: WHISPER AUDIO TRANSCRIPTION")
    print("State-of-the-art Speech-to-Text")
    print("=" * 80)
    
    # Get audio/video path from command line or prompt
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
    else:
        print("\nUsage: python download_text.py <audio_file>")
        print("\nSupported formats: MP3, WAV, FLAC, M4A, OGG, MP4, MOV, AVI")
        print("Recommended: MP3 or WAV (smaller file size, faster processing)")
        print("\nOr enter audio file path now:")
        audio_path = input("Audio file path: ").strip()
        
        if not audio_path:
            print("\nExample usage:")
            print("  python download_text.py commencement.mp3")
            print("  python download_text.py recording.wav")
            print("\nAvailable models: large-v3 (best), large-v2, medium, small, base, tiny")
            sys.exit(1)
    
    # Check if file exists
    if not os.path.exists(audio_path):
        print(f"\n❌ Error: File not found: {audio_path}")
        sys.exit(1)
    
    # Transcribe audio/video
    # For best results with names, use large-v3
    # Auto-detection will use GPU if available, otherwise CPU
    results = transcribe_audio(
        audio_path,
        model_size="large-v3",  # Best for accuracy with names
        device="auto",           # Auto-detect GPU/CPU
        compute_type="auto",     # Auto-select best compute type (int8 for CPU, float16 for GPU)
        language="en",           # Change if needed
        output_format="all"      # Generate all output formats
    )
    
    print("\n" + "=" * 80)
    print("✓ TRANSCRIPTION COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("  Step 2: python extract_metadata.py <transcript_json_file>")
    print("  Step 3: python enrich_profiles.py <metadata_json_file>")

