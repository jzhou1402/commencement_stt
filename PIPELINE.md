# Pipeline Architecture

## Overview

A three-stage pipeline for converting commencement ceremony audio into enriched graduate profiles.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT: ceremony.mp3                          │
│                      (Audio/Video of ceremony)                       │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: TRANSCRIPTION                                               │
│  Script: download_text.py                                            │
│  Model: Whisper Large V3 (1.55B params)                              │
│  Cost: FREE (runs locally)                                           │
│  Time: 2-3 hours (CPU) / 12-30 min (GPU)                             │
│                                                                       │
│  Features:                                                            │
│  • Speech-to-text with word-level timestamps                         │
│  • Voice Activity Detection (removes silence)                        │
│  • Multiple output formats (TXT, JSON, SRT, VTT)                     │
│  • Auto-detects hardware (CPU/GPU)                                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  OUTPUT FILES:                                                       │
│  • ceremony_transcript.txt     (plain text)                          │
│  • ceremony_transcript.json    (with timestamps) ← NEXT INPUT        │
│  • ceremony_transcript.srt     (subtitles)                           │
│  • ceremony_transcript.vtt     (web subtitles)                       │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: METADATA EXTRACTION                                         │
│  Script: extract_metadata.py                                         │
│  Model: GPT-4o                                                       │
│  Cost: ~$0.15-0.30                                                   │
│  Time: 30-60 seconds                                                 │
│                                                                       │
│  Extracts:                                                            │
│  • Ceremony info (institution, year, schools)                        │
│  • Graduate names (all attendees)                                    │
│  • Departments and programs                                          │
│  • Degree types and levels                                           │
│  • Structured JSON output                                            │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  OUTPUT FILE:                                                        │
│  • ceremony_transcript_metadata.json  ← NEXT INPUT                   │
│                                                                       │
│  Structure:                                                           │
│  {                                                                    │
│    "ceremony": {                                                      │
│      "institution": "MIT",                                            │
│      "year": 2025,                                                    │
│      "schools": [...]                                                 │
│    },                                                                 │
│    "graduates": [                                                     │
│      {                                                                │
│        "name": "...",                                                 │
│        "department": "...",                                           │
│        "degree_type": "...",                                          │
│        ...                                                            │
│      }                                                                │
│    ]                                                                  │
│  }                                                                    │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: PROFILE ENRICHMENT                                          │
│  Script: enrich_profiles.py                                          │
│  Model: GPT-4o with web research                                     │
│  Cost: ~$0.10-0.30 per graduate                                      │
│  Time: ~10-20 seconds per graduate                                   │
│                                                                       │
│  Researches for each graduate:                                       │
│  • Educational background                                             │
│  • LinkedIn, GitHub, personal websites                                │
│  • Academic publications                                              │
│  • Work experience                                                    │
│  • Awards and achievements                                            │
│  • Research interests                                                 │
│  • Media mentions                                                     │
│  • Professional summary                                               │
│                                                                       │
│  Optional: --sample N (test with N graduates first)                  │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  OUTPUT FILE:                                                        │
│  • ceremony_enriched.json                                            │
│                                                                       │
│  Structure:                                                           │
│  {                                                                    │
│    "ceremony": {...},                                                 │
│    "graduates": [                                                     │
│      {                                                                │
│        "name": "...",                                                 │
│        "summary": "...",                                              │
│        "online_presence": {                                           │
│          "linkedin": "...",                                           │
│          "github": "...",                                             │
│          ...                                                          │
│        },                                                             │
│        "research": {...},                                             │
│        "experience": [...],                                           │
│        "achievements": [...],                                         │
│        ...                                                            │
│      }                                                                │
│    ]                                                                  │
│  }                                                                    │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │  FINAL OUTPUT  │
                        │ Ready for use! │
                        └────────────────┘
```

## Running the Pipeline

### Option 1: Run All Steps Automatically

```bash
python run_pipeline.py ceremony.mp3
```

This runs all three steps in sequence.

### Option 2: Run Steps Individually

```bash
# Step 1: Transcription
python download_text.py ceremony.mp3

# Step 2: Metadata extraction
python extract_metadata.py ceremony_transcript.json

# Step 3: Profile enrichment
python enrich_profiles.py ceremony_transcript_metadata.json
```

This gives you more control and allows you to review output between steps.

### Option 3: Test with Sample First

```bash
# Run complete pipeline with just 5 graduates
python run_pipeline.py ceremony.mp3 --sample 5

# Or just test step 3 with sample
python enrich_profiles.py ceremony_transcript_metadata.json --sample 5
```

Recommended for testing before processing all graduates.

## Data Flow

### Input Types
- **Audio**: MP3, WAV, FLAC, M4A, OGG
- **Video**: MP4, MOV, AVI (audio extracted automatically)

### Intermediate Formats
- **JSON**: Structured data with full metadata
- **TXT**: Human-readable plain text
- **SRT/VTT**: Subtitle files for video players

### Output Format
- **JSON**: Machine-readable for databases/APIs
- Can be converted to CSV, Excel, SQL, etc.

## Cost & Time Analysis

### For 300 graduates from 1-hour ceremony:

| Step | Time | Cost | Parallelizable | Can Resume |
|------|------|------|----------------|------------|
| 1. Transcription | 2-3h (CPU) | FREE | ❌ No | ❌ No |
| 2. Metadata | 30-60s | $0.25 | ❌ No | ❌ No |
| 3. Enrichment | 50-100m | $30-90 | ✅ Yes* | ✅ Yes* |
| **Total** | **3-5h** | **$30-90** | | |

*With custom implementation

### Optimization Strategies

**Reduce transcription time:**
- Use GPU instance (AWS, GCP, Azure)
- Use smaller model (medium/small)
- Pre-process audio (denoise, normalize)

**Reduce enrichment cost:**
- Use --sample to test first
- Process in batches
- Cache results for re-runs
- Use cheaper models for initial pass

**Reduce enrichment time:**
- Increase concurrent requests (with rate limiting)
- Process only high-priority graduates first
- Skip low-confidence matches

## Error Handling

### Transcription Failures
- Audio quality issues → Pre-process audio
- Out of memory → Use smaller model
- Hardware errors → Check GPU drivers

### Metadata Extraction Failures
- API errors → Check API key and limits
- Parse errors → Check transcript format
- Incomplete data → Review transcript quality

### Enrichment Failures
- Rate limits → Increase delay between requests
- API timeouts → Retry failed requests
- Low confidence → Manual review needed

## Quality Metrics

### Transcription Quality
- **Excellent**: 95-98% accuracy (clear audio, good mic)
- **Good**: 90-95% accuracy (typical ceremony audio)
- **Fair**: 80-90% accuracy (noisy, multiple speakers)
- **Poor**: <80% accuracy (very noisy, echo, distant)

### Metadata Extraction Quality
- **Accuracy**: 95-98% (GPT-4o is very reliable)
- **Completeness**: Depends on transcript quality
- **False positives**: Very rare with GPT-4o

### Enrichment Quality
- **High confidence**: Strong online presence, multiple sources
- **Medium confidence**: Some online presence, single source
- **Low confidence**: Minimal online presence, inferred data

## Use Cases

### 1. Alumni Relations
- Track graduates for engagement
- Segment by interests/industry
- Personalized outreach campaigns

### 2. Recruiting
- Identify top talent by research/skills
- Match candidates to opportunities
- Verify backgrounds

### 3. Research & Analytics
- Study graduate career trajectories
- Analyze trends by department/year
- Measure program success

### 4. Networking
- Connect graduates with similar interests
- Find mentors for current students
- Build alumni communities

### 5. Development (Fundraising)
- Identify successful alumni
- Track career progression
- Segment for campaigns

## Data Privacy & Ethics

### What We Collect
- ✅ Publicly available information only
- ✅ Information from commencement (already public)
- ❌ No private/protected information
- ❌ No unauthorized scraping

### Best Practices
1. **Transparency**: Inform graduates about data collection
2. **Opt-out**: Provide mechanism to remove profiles
3. **Accuracy**: Regular updates and corrections
4. **Security**: Protect stored data appropriately
5. **Purpose limitation**: Use only for stated purposes

### Legal Considerations
- Comply with GDPR, CCPA, and local laws
- Respect robots.txt and terms of service
- Obtain consent when required
- Provide data access and deletion rights

## Advanced Usage

### Batch Processing Multiple Ceremonies

```bash
for ceremony in ceremonies/*.mp3; do
  python run_pipeline.py "$ceremony"
done
```

### Export to Database

```python
import json
import psycopg2

with open('ceremony_enriched.json') as f:
    data = json.load(f)

# Insert into PostgreSQL
conn = psycopg2.connect("dbname=alumni")
cur = conn.cursor()
for grad in data['graduates']:
    cur.execute("""
        INSERT INTO graduates (name, degree, linkedin, ...)
        VALUES (%s, %s, %s, ...)
    """, (grad['name'], grad['degree_info']['degree'], ...))
conn.commit()
```

### Custom Enrichment Logic

```python
from enrich_profiles import enrich_graduate_profile
from openai import OpenAI

client = OpenAI(api_key="...")

# Custom enrichment for specific needs
for graduate in graduates:
    profile = enrich_graduate_profile(
        graduate,
        ceremony_info,
        client,
        use_web_search=True
    )
    # Add custom processing
    profile['custom_field'] = compute_custom_metric(profile)
```

## Troubleshooting

See [README.md](README.md) for detailed troubleshooting guide.

## Future Enhancements

- [ ] Web interface for easy use
- [ ] Real-time processing (streaming)
- [ ] Multi-language support
- [ ] Integration with CRM systems
- [ ] Automated updates (track career changes)
- [ ] Social media integration
- [ ] Batch processing optimization
- [ ] Custom search API integration


