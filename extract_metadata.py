#!/usr/bin/env python3
"""
Extract Graduate Names and Metadata from Transcript

Takes a transcript text file and extracts all graduate names with their
affiliated information (department, degree, program, etc.)

Usage:
    python extract_metadata.py <transcript_file> <school> <year>
    
Examples:
    python extract_metadata.py test_audio/mit_2025_transcript.txt MIT 2025
    python extract_metadata.py test_audio/mit_2025_transcript.json MIT 2025
"""

import os
import sys
import json
from pathlib import Path
from openai import OpenAI


def load_transcript(transcript_path):
    """Load transcript from TXT or JSON file"""
    path = Path(transcript_path)
    
    with open(path, 'r', encoding='utf-8') as f:
        if path.suffix == '.json':
            data = json.load(f)
            # Extract text from JSON
            if isinstance(data, dict):
                text = data.get('full_text', '') or data.get('text', '')
                if not text and 'segments' in data:
                    # Reconstruct from segments
                    text = ' '.join(seg.get('text', '') for seg in data['segments'])
            else:
                text = str(data)
        else:
            # Plain text file
            text = f.read()
    
    return text.strip()


BOUNDARY_SYSTEM_PROMPT = """You are analyzing a commencement ceremony transcript to find where different academic programs/departments are announced.

In commencement ceremonies, an announcer reads department/program announcements like:
- "In the School of Engineering, the Department of Civil and Environmental Engineering, master of engineering..."
- "Doctor of Philosophy in Electrical Engineering and Computer Science"
- "Master of Science in Mechanical Engineering"

These announcements are followed by lists of graduate names.

Your task: Find ALL segment indices where a new department/program/degree is announced.

You will receive a numbered list of transcript segments. Return a JSON object:
{{
  "boundaries": [
    {{
      "segment_index": 42,
      "program_description": "Full text of the department/program/degree announcement"
    }}
  ]
}}

Rules:
1. Only mark segments that announce a NEW program/department/degree group
2. Do NOT mark segments that are just graduate names
3. Include the full announcement text as program_description
4. If no program boundaries exist in this text, return {{"boundaries": []}}"""

EXTRACTION_SYSTEM_PROMPT = """You are an expert at extracting graduate names from commencement transcripts.

This chunk of transcript is from a {school} {year} commencement ceremony.
The broader context is: {program_context}

Within this chunk, the announcer reads specific degree programs (e.g. "Bachelor of Science in Material Science and Engineering") followed by graduate names. A single chunk may contain MULTIPLE programs.

Extract ALL graduates grouped by their specific program. Pay close attention to degree and major announcements that appear WITHIN the text — these tell you exactly what program each group of names belongs to.

Return a JSON object:
{{
  "groups": [
    {{
      "program": "The specific degree + major (e.g. 'Bachelor of Science in Electrical Engineering and Computer Science')",
      "names": ["Student Name 1", "Student Name 2", ...]
    }}
  ]
}}

Rules:
1. Extract ONLY graduate names (not faculty, speakers, staff, or performers)
2. Be comprehensive - capture ALL names
3. Preserve exact name spelling from transcript
4. Group names by their specific program/major as announced in the transcript
5. If there are no graduate names in this chunk, return {{"groups": []}}"""


def find_program_boundaries(segments, school, year, client, on_status=None):
    """
    Use LLM to identify segment indices where new programs/departments are announced.

    Returns list of {"segment_index": int, "program_description": str}
    """
    # Build a numbered segment list for the LLM
    # For very long transcripts, we may need to batch this too
    seg_lines = []
    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if text:
            seg_lines.append(f"[{i}] {text}")

    seg_text = "\n".join(seg_lines)

    # If transcript is very long, split the boundary detection into batches
    max_chars = 60000
    if len(seg_text) <= max_chars:
        batches = [seg_text]
    else:
        batches = []
        current = []
        current_len = 0
        for line in seg_lines:
            if current_len + len(line) > max_chars and current:
                batches.append("\n".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line) + 1
        if current:
            batches.append("\n".join(current))

    all_boundaries = []
    for batch_i, batch in enumerate(batches):
        if on_status:
            on_status(f"Finding program boundaries (batch {batch_i+1}/{len(batches)})...")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": BOUNDARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Find all program/department announcement segments in this {school} {year} commencement transcript:\n\n{batch}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads(response.choices[0].message.content)
        all_boundaries.extend(data.get("boundaries", []))

    return all_boundaries


def chunk_by_program(segments, boundaries):
    """
    Split segments into chunks based on program boundaries.
    Each chunk is (program_description, segment_list).
    """
    if not boundaries:
        # No boundaries found — return everything as one chunk
        full_text = " ".join(s.get("text", "") for s in segments)
        return [("Unknown program", full_text)]

    # Sort boundaries by segment_index
    boundaries = sorted(boundaries, key=lambda b: b["segment_index"])

    chunks = []

    # Any segments before first boundary (preamble — speeches, etc.)
    first_idx = boundaries[0]["segment_index"]
    if first_idx > 0:
        preamble = " ".join(s.get("text", "") for s in segments[:first_idx])
        if preamble.strip():
            chunks.append(("Preamble (speeches, introductions)", preamble))

    # Chunk between each boundary
    for i, boundary in enumerate(boundaries):
        start_idx = boundary["segment_index"]
        end_idx = boundaries[i + 1]["segment_index"] if i + 1 < len(boundaries) else len(segments)
        chunk_text = " ".join(s.get("text", "") for s in segments[start_idx:end_idx])
        if chunk_text.strip():
            chunks.append((boundary["program_description"], chunk_text))

    return chunks


def _extract_groups_from_chunk(chunk_text, program_context, school, year, client):
    """Extract groups of names with their specific programs from a chunk."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": EXTRACTION_SYSTEM_PROMPT.format(
                    school=school, year=year, program_context=program_context
                ),
            },
            {
                "role": "user",
                "content": f"Extract ALL graduate names grouped by program from this transcript chunk:\n\n{chunk_text}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    data = json.loads(response.choices[0].message.content)
    groups = data.get("groups", [])
    # Normalize: ensure each group has "description" key for downstream compat
    for g in groups:
        if "program" in g and "description" not in g:
            g["description"] = g.pop("program")
    return groups


def extract_groups_chunked(transcript_data, school, year, api_key=None, on_progress=None):
    """
    Extract graduate groups from transcript using smart program-boundary chunking.

    1. Finds program/department announcement boundaries in the transcript
    2. Chunks transcript at those boundaries
    3. Extracts names from each chunk with full program context

    Args:
        transcript_data: Either a string (plain text) or a dict with 'segments' and 'full_text'
        school: Institution name
        year: Graduation year
        api_key: OpenAI API key
        on_progress: Optional callback(chunk_index, total_chunks, groups_so_far)

    Returns:
        List of all groups across all chunks
    """
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)

    # Get segments
    if isinstance(transcript_data, dict) and "segments" in transcript_data:
        segments = transcript_data["segments"]
    else:
        # Plain text fallback — wrap in a single segment
        text = transcript_data if isinstance(transcript_data, str) else str(transcript_data)
        segments = [{"start": 0, "end": 0, "text": text}]

    def on_status(msg):
        if on_progress:
            on_progress(0, 1, [], msg)

    # Step 1: Find program boundaries
    on_status("Identifying program/department boundaries...")
    boundaries = find_program_boundaries(segments, school, year, client, on_status=on_status)
    print(f"  Found {len(boundaries)} program boundaries", flush=True)

    # Step 2: Chunk by program
    program_chunks = chunk_by_program(segments, boundaries)
    print(f"  Split into {len(program_chunks)} program chunks", flush=True)

    # Step 3: Extract names from each chunk
    all_groups = []
    total = len(program_chunks)

    for i, (program_desc, chunk_text) in enumerate(program_chunks):
        if not chunk_text.strip():
            continue

        # Skip preamble chunks (speeches, not name-reading)
        if program_desc.startswith("Preamble"):
            if on_progress:
                on_progress(i + 1, total, all_groups)
            continue

        groups = _extract_groups_from_chunk(chunk_text, program_desc, school, year, client)
        all_groups.extend(groups)

        if on_progress:
            on_progress(i + 1, total, all_groups)

    return all_groups


def extract_groups_from_transcript(transcript_text, school, year, api_key=None):
    """
    Extract graduate groups (single-call, for CLI / backward compat).
    For chunked extraction with progress, use extract_groups_chunked().
    """
    return extract_groups_chunked(transcript_text, school, year, api_key=api_key)


def convert_groups_to_graduates(groups, school, year):
    """
    Convert groups format to structured graduates list.
    Uses the group description directly as the program — no brittle parsing.
    """
    graduates = []

    for group in groups:
        description = group.get("description", "Unknown")
        names = group.get("names", [])

        for name in names:
            if name and name.strip():
                graduates.append({
                    "name": name.strip(),
                    "degree": description,
                })

    return {
        "school": school,
        "year": year,
        "graduates": graduates
    }


def main():
    print("=" * 80)
    print("EXTRACT GRADUATE NAMES AND METADATA")
    print("=" * 80)
    
    # Parse arguments
    if len(sys.argv) != 4:
        print("\n❌ Error: Invalid arguments")
        print("\nUsage:")
        print("  python extract_metadata.py <transcript_file> <school> <year>")
        print("\nExamples:")
        print("  python extract_metadata.py test_audio/mit_2025_transcript.txt MIT 2025")
        print("  python extract_metadata.py test_audio/mit_2025_transcript.json MIT 2025")
        sys.exit(1)
    
    transcript_path = sys.argv[1]
    school = sys.argv[2]
    year = int(sys.argv[3])
    
    # Check if file exists
    if not os.path.exists(transcript_path):
        print(f"\n❌ Error: File not found: {transcript_path}")
        sys.exit(1)
    
    # Load transcript
    print(f"\n📖 Loading transcript: {transcript_path}")
    transcript_text = load_transcript(transcript_path)
    print(f"✓ Loaded transcript ({len(transcript_text):,} characters)")
    
    # Extract groups (description + names)
    groups = extract_groups_from_transcript(transcript_text, school, year)
    
    print(f"\n✓ Extracted {len(groups)} graduate groups")
    
    # Convert groups to structured metadata
    print("📊 Parsing descriptions and organizing data...")
    data = convert_groups_to_graduates(groups, school, year)
    
    # Display summary
    graduates = data.get("graduates", [])
    
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    
    print(f"\n🎓 Ceremony: {school} {year}")
    print(f"📦 Groups extracted: {len(groups)}")
    print(f"👥 Total graduates: {len(graduates)}")
    
    # Show groups summary
    print(f"\n📋 Groups (first 5):")
    for i, group in enumerate(groups[:5], 1):
        desc = group.get('description', 'No description')
        names_count = len(group.get('names', []))
        # Truncate long descriptions
        if len(desc) > 80:
            desc = desc[:77] + "..."
        print(f"  {i}. {desc}")
        print(f"     → {names_count} graduates")
    
    if len(groups) > 5:
        print(f"  ... and {len(groups) - 5} more groups")
    
    # Count by degree
    degree_counts = {}
    for grad in graduates:
        degree = grad.get('degree', 'Unknown')
        degree_counts[degree] = degree_counts.get(degree, 0) + 1

    if degree_counts:
        print("\n📊 By degree:")
        for degree, count in sorted(degree_counts.items()):
            print(f"  - {degree}: {count}")

    # Show sample graduates
    print(f"\n👤 Sample graduates (first 10):")
    for i, grad in enumerate(graduates[:10], 1):
        degree = grad.get('degree', '?')
        name = grad['name'][:35] + "..." if len(grad['name']) > 35 else grad['name']
        print(f"  {i:2d}. {name:<38} | {degree}")
    
    if len(graduates) > 10:
        print(f"  ... and {len(graduates) - 10} more")
    
    # Save metadata
    transcript_path = Path(transcript_path)
    output_filename = f"{school.lower()}_{year}_graduates.json"
    output_path = transcript_path.parent / output_filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Saved metadata to: {output_path}")
    
    print("\n" + "=" * 80)
    print("Next step:")
    print(f"  python enrich_profiles.py {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()

