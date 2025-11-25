# Commencement Speech-to-Text & Profile Enrichment Pipeline

A complete pipeline for transcribing commencement ceremonies and building comprehensive graduate profiles using state-of-the-art AI.

## 🎯 What This Does

1. **Transcribes audio/video** using Whisper Large V3 (SOTA speech-to-text)
2. **Extracts structured metadata** (names, degrees, departments) using GPT-4o
3. **Enriches profiles** with deep online research for each graduate

Perfect for:
- Alumni offices tracking graduates
- Recruiters building candidate databases
- Researchers studying graduate outcomes
- Network building and connections

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key (required for steps 2 & 3)
export OPENAI_API_KEY="sk-your-api-key-here"
```

### Complete Pipeline

```bash
# Step 1: Transcribe audio (FREE - runs locally)
python download_text.py ceremony.mp3

# Step 2: Extract metadata (~$0.15-0.30)
python extract_metadata.py ceremony_transcript.json

# Step 3: Enrich profiles (~$0.10-0.30 per person)
python enrich_profiles.py ceremony_metadata.json

# Or test with a sample first:
python enrich_profiles.py ceremony_metadata.json --sample 5
```

## 📋 Pipeline Details

### Step 1: Audio Transcription

**Script:** `download_text.py`

Converts audio/video to text using OpenAI's Whisper Large V3 model.

**Features:**
- Supports: MP3, WAV, FLAC, M4A, OGG, MP4, MOV, AVI
- Word-level timestamps
- Voice Activity Detection (filters silence)
- Auto-detects GPU/CPU and optimizes accordingly

**Output:**
- `*_transcript.txt` - Plain text
- `*_transcript.json` - Detailed with timestamps
- `*_transcript.srt` - Subtitles
- `*_transcript.vtt` - Web subtitles

**Example:**
```bash
python download_text.py commencement.mp3
```

**Performance:**
- CPU (Mac): ~0.3-0.5x realtime (1hr audio = 2-3hrs processing)
- GPU (NVIDIA): ~2-5x realtime (1hr audio = 12-30min processing)
- Cost: FREE (runs locally)

### Step 2: Metadata Extraction

**Script:** `extract_metadata.py`

Extracts structured data from transcript using GPT-4o.

**What it extracts:**
- Ceremony info (institution, year, type)
- All graduate names
- Departments and programs
- Degree levels and types
- Full degree names

**Output:**
- `*_metadata.json` - Structured graduate data

**Example:**
```bash
python extract_metadata.py ceremony_transcript.json
```

**Cost:** ~$0.15-0.30 per ceremony (depending on length)

### Step 3: Profile Enrichment

**Script:** `enrich_profiles.py`

Conducts deep online research on each graduate using GPT-4o.

**What it finds:**
- Educational background
- LinkedIn, GitHub, personal websites
- Academic publications
- Work experience
- Awards and achievements
- Research interests
- Media mentions
- Professional summary

**Output:**
- `*_enriched.json` - Complete profiles with sources

**Example:**
```bash
# Process all graduates
python enrich_profiles.py ceremony_metadata.json

# Test with 5 graduates first
python enrich_profiles.py ceremony_metadata.json --sample 5
```

**Performance:**
- ~10-20 seconds per graduate
- For 300 graduates: ~50-100 minutes
- Uses rate limiting to avoid API throttling

**Cost:** ~$0.10-0.30 per graduate

## 💰 Cost Breakdown

For a typical commencement with 300 graduates:

| Step | Cost | Time |
|------|------|------|
| 1. Transcription | FREE | 2-3 hours (CPU) |
| 2. Metadata | ~$0.25 | 30-60 seconds |
| 3. Enrichment | ~$30-90 | 50-100 minutes |
| **Total** | **~$30-90** | **~3-5 hours** |

## 📊 Output Format

### Metadata JSON Structure

```json
{
  "ceremony": {
    "institution": "MIT",
    "year": 2025,
    "ceremony_type": "Advanced Degree Ceremony",
    "schools": ["School of Engineering", "Schwarzman College of Computing"]
  },
  "graduates": [
    {
      "name": "John Doe",
      "department": "Electrical Engineering and Computer Science",
      "program": "Artificial Intelligence",
      "degree_level": "Doctoral",
      "degree_type": "PhD",
      "degree_full": "Doctor of Philosophy in Electrical Engineering and Computer Science"
    }
  ]
}
```

### Enriched Profile Structure

```json
{
  "name": "John Doe",
  "degree_info": {...},
  "education": [...],
  "online_presence": {
    "linkedin": "https://linkedin.com/in/johndoe",
    "github": "https://github.com/johndoe",
    "personal_website": "https://johndoe.com",
    "google_scholar": "..."
  },
  "research": {
    "interests": ["Machine Learning", "Computer Vision"],
    "publications": [...],
    "thesis_topic": "..."
  },
  "experience": [...],
  "achievements": [...],
  "projects": [...],
  "media_mentions": [...],
  "summary": "PhD graduate specializing in...",
  "research_confidence": "high"
}
```

## 🔧 Configuration

### Model Selection

**Transcription (Step 1):**
```python
# In download_text.py, line ~327
model_size="large-v3"  # Best accuracy
# Options: large-v3, large-v2, medium, small, base, tiny
```

**Metadata & Enrichment (Steps 2 & 3):**
- Uses GPT-4o (latest OpenAI model)
- Automatic - no configuration needed

### Rate Limiting

**Enrichment (Step 3):**
```python
# In enrich_profiles.py, line ~345
delay=1.0  # Seconds between API calls
```

Adjust based on your API rate limits.

## 📁 File Structure

```
commencement_stt/
├── download_text.py          # Step 1: Transcription
├── extract_metadata.py       # Step 2: Metadata extraction
├── enrich_profiles.py        # Step 3: Profile enrichment
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── test_audio/
    ├── ceremony.mp3          # Input audio
    ├── ceremony_transcript.json
    ├── ceremony_metadata.json
    └── ceremony_enriched.json
```

## 🔍 Use Cases

### 1. Alumni Relations
Track graduates for newsletters, fundraising, and engagement.

### 2. Recruiting
Build a database of talented graduates with verified backgrounds.

### 3. Research
Study graduate career trajectories and outcomes.

### 4. Networking
Connect graduates with similar interests or backgrounds.

### 5. Communications
Create personalized outreach based on interests and achievements.

## ⚠️ Important Notes

### Privacy & Ethics
- Only uses publicly available information
- Respects robots.txt and terms of service
- No personal data collection beyond public profiles
- Graduates have right to request removal

### Accuracy
- Transcription: ~90-95% accurate (names may have typos)
- Metadata: ~95-98% accurate (GPT-4o is very reliable)
- Enrichment: Varies by online presence (marked by confidence level)

### API Costs
- Requires OpenAI API key (paid)
- Costs scale with number of graduates
- Test with --sample flag first

## 🐛 Troubleshooting

### "ValueError: Requested float16 compute type"
- Fixed automatically - script now uses int8 for CPU
- If issue persists, ensure you have latest code

### "No OpenAI API key found"
- Set environment variable: `export OPENAI_API_KEY="sk-..."`
- Or add to ~/.zshrc for persistence

### "Rate limit exceeded"
- Increase delay in enrich_profiles.py
- Check your OpenAI API tier and limits
- Consider processing in batches

### Transcription too slow
- Use smaller model: `model_size="medium"` or `"small"`
- Use higher quality audio (reduces re-processing)
- Consider GPU instance if processing many files

## 📚 Technical Details

### Models Used
- **Whisper Large V3**: 1.55B parameters, trained on 680K hours
- **GPT-4o**: OpenAI's latest multimodal model (Oct 2024)

### Dependencies
- faster-whisper: Optimized Whisper implementation
- openai: Official OpenAI Python client
- torch: PyTorch for model inference
- numpy: Numerical operations

## 🤝 Contributing

Suggestions for improvement:
- Add more search APIs (Perplexity, Tavily, SerpAPI)
- Support for other languages
- Batch processing multiple ceremonies
- Database integration (PostgreSQL, MongoDB)
- Web interface for easy use

## 📝 License

MIT License - Use freely for any purpose.

## 🙏 Acknowledgments

- OpenAI (Whisper & GPT-4o)
- CTranslate2 team (faster-whisper)
- MIT for inspiring this project


