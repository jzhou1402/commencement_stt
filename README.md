# Commencement Speech-to-Text & Profile Enrichment Pipeline

A pipeline for transcribing commencement ceremonies and building graduate profiles using AI.

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-your-api-key-here"
```

## Usage

### Run the full pipeline

```bash
python run_pipeline.py ceremony.mp3 MIT 2025

# Test with a small sample first
python run_pipeline.py ceremony.mp3 MIT 2025 --sample 5
```

### Or run each step individually

```bash
# Step 1: Transcribe audio (free, runs locally with Whisper Large V3)
python download_text.py ceremony.mp3

# Step 2: Extract graduate names and metadata (GPT-4o, ~$0.25)
python extract_metadata.py ceremony_transcript.txt MIT 2025

# Step 3: Enrich profiles with web research (GPT-5.1 Responses API, ~$0.10-0.30/person)
python enrich_profiles.py mit_2025_graduates.json --sample 5   # test first
python enrich_profiles.py mit_2025_graduates.json              # then all
python enrich_profiles.py mit_2025_graduates.json "Jane Smith" # or one person
```

## Pipeline

```
ceremony.mp3
  |
  v
[Step 1: download_text.py] -- Whisper Large V3, local, free
  |  outputs: *_transcript.{txt,json,srt,vtt}
  v
[Step 2: extract_metadata.py <transcript> <school> <year>] -- GPT-4o
  |  outputs: {school}_{year}_graduates.json
  v
[Step 3: enrich_profiles.py <graduates.json>] -- GPT-5.1 + web search + reasoning
  |  outputs: {school}_{year}_enriched.json
  v
Done: enriched profiles with LinkedIn, GitHub, publications, experience, etc.
```

## Step details

### Step 1: Transcription (`download_text.py`)

Converts audio/video to text using Whisper Large V3. Supports MP3, WAV, FLAC, M4A, OGG, MP4, MOV, AVI.

- Word-level timestamps
- Voice Activity Detection (filters silence)
- Auto-detects GPU/CPU
- Outputs: plain text, JSON with timestamps, SRT subtitles, VTT subtitles
- Performance: ~2-3hrs for 1hr audio on CPU, ~12-30min on GPU

### Step 2: Metadata extraction (`extract_metadata.py`)

Extracts structured graduate data from the transcript using GPT-4o.

```bash
python extract_metadata.py <transcript_file> <school> <year>
```

Extracts groups of graduates by department/program, then parses each into:
- Name, department, degree type/level, school within university

### Step 3: Profile enrichment (`enrich_profiles.py`)

Researches each graduate using the OpenAI Responses API with GPT-5.1, high reasoning, and web search.

```bash
python enrich_profiles.py <graduates_json>              # all
python enrich_profiles.py <graduates_json> --sample N   # first N
python enrich_profiles.py <graduates_json> "Full Name"  # one person
```

Produces free-form profiles with citations covering education, experience, publications, online presence, and achievements.

## Cost estimate (300 graduates, 1hr ceremony)

| Step | Time | Cost |
|------|------|------|
| Transcription | 2-3hrs (CPU) | Free |
| Metadata extraction | 30-60s | ~$0.25 |
| Profile enrichment | 50-100min | ~$30-90 |

## Test data

`test_audio/mit_2025_graduates.json` contains extracted metadata for 300+ MIT 2025 graduates, ready for enrichment testing.

## Troubleshooting

- **"No OpenAI API key"**: `export OPENAI_API_KEY="sk-..."`
- **Transcription too slow**: Use `model_size="medium"` or `"small"` in `download_text.py`
- **Rate limit exceeded**: Increase `time.sleep()` delay in `enrich_profiles.py`
- **"ValueError: Requested float16 compute type"**: Handled automatically (uses int8 on CPU)

## License

MIT
