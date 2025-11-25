# Quick Start Guide

## Setup (One Time)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your OpenAI API key
export OPENAI_API_KEY="sk-your-key-here"

# Optional: Add to ~/.zshrc for persistence
echo 'export OPENAI_API_KEY="sk-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

## Run the Pipeline

```bash
# STEP 1: Transcribe audio (OPTIONAL - runs locally, FREE)
python download_text.py your_ceremony.mp3

# This creates:
# - your_ceremony_transcript.txt  ← Use this for step 2
# - your_ceremony_transcript.json
# - your_ceremony_transcript.srt
# - your_ceremony_transcript.vtt

# STEP 2: Extract names and metadata (~$0.25, 30-60 seconds)
python extract_metadata.py your_ceremony_transcript.txt MIT 2025

# Arguments: <transcript_file> <school> <year>
# This creates:
# - mit_2025_graduates.json  ← Use this for step 3

# STEP 3: Enrich each graduate profile (~$0.10-0.30 per person)
# Test with 5 people first:
python enrich_profiles.py mit_2025_graduates.json --sample 5

# Or process everyone (takes time!):
python enrich_profiles.py mit_2025_graduates.json

# This creates:
# - mit_2025_enriched.json  ← Final output!
```

## Pipeline Flow

```
ceremony.mp3 (or existing transcript.txt)
    ↓
[Step 1: Transcription - Whisper Large V3] ← OPTIONAL
    ↓
ceremony_transcript.txt (plain text)
    ↓
[Step 2: Extract Names - GPT-4o]
  Input: transcript.txt + school + year
    ↓
mit_2025_graduates.json (list of names with metadata)
    ↓
[Step 3: Enrich Each Profile - GPT-4o + Web Research]
    ↓
mit_2025_enriched.json (comprehensive profiles)
```

## Expected Timeline

For a 1-hour ceremony with 300 graduates:

| Step | Time | Cost | Can Stop? |
|------|------|------|-----------|
| 1. Transcription | 2-3 hours | FREE | ❌ Must complete |
| 2. Metadata | 30-60 sec | ~$0.25 | ❌ Fast anyway |
| 3. Enrichment | 50-100 min | ~$30-90 | ✅ Can resume |

## Tips

### Starting Out
1. **Test with --sample first**: `--sample 5` to verify output quality
2. **Check transcription quality**: Review `*_transcript.txt` before proceeding
3. **Monitor costs**: Each graduate costs ~$0.10-0.30 in Step 3

### For Large Ceremonies
1. **Process in batches**: Use `--sample` to process chunks
2. **Run overnight**: Enrichment takes time but doesn't need monitoring
3. **Save intermediate results**: Each step saves output, can resume if interrupted

### Audio Quality
- **Best**: MP3 at 128kbps or higher
- **Good enough**: Any clear speech recording
- **Problems**: Very noisy audio may need preprocessing

## Troubleshooting

**"No OpenAI API key"**
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**"File not found"**
- Check file paths
- Use tab completion
- Try absolute paths

**Transcription taking forever**
- Normal on CPU! 1hr audio = 2-3hrs processing
- Consider using smaller model: Edit download_text.py line ~327
- Change `model_size="large-v3"` to `"medium"` or `"small"`

**API rate limits**
- Increase delay in enrich_profiles.py (line ~345)
- Process smaller batches with `--sample`
- Check your OpenAI tier limits

## What You Get

### After Step 1 (Transcription)
- Perfect for reading/searching the ceremony
- Can manually find names if needed
- Usable subtitles for video

### After Step 2 (Metadata)
- Clean list of all graduates
- Organized by department
- Degree information
- Ready for mail merge or basic outreach

### After Step 3 (Enrichment)
- Full professional profiles
- Contact information (LinkedIn, etc.)
- Research interests and publications
- Work history
- Ready for recruiting, networking, or alumni relations

## Example: Using Existing Transcript

If you already have a transcript (like in `test_audio/`):

```bash
# Skip step 1, start with extraction
python extract_metadata.py test_audio/mit_2025_transcript.txt MIT 2025

# Then enrich
python enrich_profiles.py mit_2025_graduates.json --sample 5
```

## Example Output

### Step 2: Graduates List
```json
{
  "school": "MIT",
  "year": 2025,
  "graduates": [
    {
      "name": "Jane Smith",
      "department": "Electrical Engineering and Computer Science",
      "degree_type": "PhD",
      "degree_level": "Doctoral",
      "program": "Artificial Intelligence"
    }
  ]
}
```

### Step 3: Enriched Profile
```json
{
  "name": "Jane Smith",
  "degree_info": {...},
  "summary": "PhD graduate specializing in ML and CV...",
  "online_presence": {
    "linkedin": "https://linkedin.com/in/janesmith",
    "github": "https://github.com/janesmith"
  },
  "research": {
    "interests": ["Machine Learning", "Computer Vision"],
    "publications": [...]
  }
}
```

## Next Steps

1. **Export to Excel**: Use `jq` or Python to convert JSON to CSV
2. **Import to CRM**: Most systems accept JSON or CSV
3. **Build website**: Create alumni directory
4. **Recruiting**: Search by skills/interests
5. **Networking**: Connect people with similar backgrounds

## Need Help?

- Check README.md for detailed documentation
- Review the example files in test_audio/
- Test with --sample flag before processing all graduates

