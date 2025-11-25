# Demo: Extract and Enrich MIT 2025 Graduates

## Quick Demo (Using Existing Transcript)

You already have a transcript in `test_audio/mit_2025_transcript.txt`!

### Step 1: Extract Names and Metadata

```bash
python extract_metadata.py test_audio/mit_2025_transcript.txt MIT 2025
```

**What this does:**
- Reads the transcript text
- Uses GPT-4o to extract ALL graduate names
- For each name, identifies their:
  - Department (e.g., "Electrical Engineering and Computer Science")
  - Degree type (e.g., "PhD", "MS", "MEng")
  - Degree level (e.g., "Doctoral", "Master's")
  - Program (e.g., "Artificial Intelligence")
  - School within MIT (e.g., "School of Engineering")

**Output:** `test_audio/mit_2025_graduates.json`

**Example output:**
```json
{
  "school": "MIT",
  "year": 2025,
  "graduates": [
    {
      "name": "Raza Abbas",
      "department": "Electrical Engineering and Computer Science",
      "degree_type": "MEng",
      "degree_level": "Master's",
      "program": null,
      "school_within": "Schwarzman College of Computing"
    },
    {
      "name": "Ming Chen",
      "department": "Electrical Engineering and Computer Science",
      "degree_type": "MEng",
      "degree_level": "Master's",
      ...
    }
  ]
}
```

### Step 2: Enrich Profiles (Test with 5 people)

```bash
python enrich_profiles.py test_audio/mit_2025_graduates.json --sample 5
```

**What this does:**
- Takes the first 5 graduates from the list
- For each person, uses GPT-4o to:
  - Search for their LinkedIn profile
  - Find their GitHub if they have one
  - Look for academic publications
  - Research their background and experience
  - Compile a professional summary

**Output:** `test_audio/mit_2025_enriched.json`

**Example enriched profile:**
```json
{
  "name": "Raza Abbas",
  "degree_info": {
    "degree": "MEng",
    "department": "Electrical Engineering and Computer Science",
    "institution": "MIT",
    "year": 2025
  },
  "summary": "Master of Engineering graduate from MIT specializing in...",
  "online_presence": {
    "linkedin": "https://linkedin.com/in/razaabbas",
    "github": "https://github.com/razaabbas",
    "personal_website": null,
    "google_scholar": null
  },
  "research": {
    "interests": ["Machine Learning", "Software Engineering"],
    "publications": [],
    "thesis_topic": null
  },
  "experience": [
    {
      "role": "Software Engineer Intern",
      "company": "Google",
      "duration": "Summer 2024",
      "description": "..."
    }
  ],
  "achievements": [],
  "projects": [],
  "media_mentions": [],
  "research_confidence": "medium"
}
```

### Step 3: Process Everyone (300+ people)

Once you're happy with the sample results:

```bash
python enrich_profiles.py test_audio/mit_2025_graduates.json
```

**Time:** ~50-100 minutes for 300 graduates  
**Cost:** ~$30-90 total

## Full Workflow Summary

```bash
# If you need to transcribe audio first:
python download_text.py ceremony.mp3

# Extract names with metadata
python extract_metadata.py ceremony_transcript.txt MIT 2025

# Test with 5 people
python enrich_profiles.py mit_2025_graduates.json --sample 5

# Review results
cat mit_2025_enriched.json | jq '.graduates[0]'

# If good, process everyone
python enrich_profiles.py mit_2025_graduates.json
```

## Key Advantages of This Approach

1. **Simple & Clear**
   - Two scripts, two steps
   - Clear inputs and outputs
   - Easy to understand

2. **Flexible**
   - Can use existing transcripts (skip step 1)
   - Can test with --sample before processing all
   - Can edit graduates.json before enriching

3. **Cost Effective**
   - Step 1 (transcription) is FREE
   - Step 2 (extraction) is ~$0.25 total
   - Step 3 (enrichment) only charges per person processed

4. **Resumable**
   - Can stop and resume enrichment
   - Can process in batches
   - Can re-run without re-transcribing

## Tips

### Before Running
- Set `OPENAI_API_KEY` environment variable
- Test with `--sample 5` first
- Review extraction quality before enriching

### During Processing
- Enrichment takes time (~10-20 sec per person)
- Can Ctrl+C to stop (saves what's done)
- Monitor costs on OpenAI dashboard

### After Processing
- Review confidence scores
- Manually verify low-confidence profiles
- Export to Excel/CSV for analysis

## Cost Breakdown

For MIT 2025 ceremony (~300 graduates):

| Step | Cost | Time |
|------|------|------|
| Extract names | $0.25 | 30 sec |
| Enrich 5 (test) | $0.50-1.50 | 1 min |
| Enrich all 300 | $30-90 | 50-100 min |

## Next Steps

1. Run extraction on existing transcript
2. Review graduates.json for accuracy
3. Test enrichment with --sample 5
4. Process all graduates
5. Export and use the data!


