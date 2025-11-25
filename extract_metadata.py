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


def extract_groups_from_transcript(transcript_text, school, year, api_key=None):
    """
    Extract graduate groups (department/program + names list)
    
    Args:
        transcript_text: Full transcript text
        school: Institution name
        year: Graduation year
        api_key: OpenAI API key
    
    Returns:
        List of groups with descriptions and names
    """
    
    # Get API key
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        print("\n❌ Error: No OpenAI API key found!")
        print("Set OPENAI_API_KEY environment variable")
        print("\nExample:")
        print('  export OPENAI_API_KEY="sk-your-api-key-here"')
        sys.exit(1)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    print(f"\n🤖 Extracting graduate groups from {school} {year} ceremony...")
    print("   Using GPT-4o for extraction...")
    
    # Extract groups
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are an expert at extracting graduate names from commencement transcripts.

In commencement ceremonies, graduates are typically announced in groups by department/program/degree.
The pattern is usually:
1. An announcement like "In the School of Engineering, the Department of Civil and Environmental Engineering, master of engineering in civil and environmental engineering"
2. Followed by a list of graduate names

Your task: Extract ALL such groups from this {school} {year} transcript.

Return a JSON object with this structure:
{{
  "groups": [
    {{
      "description": "Full description of the department/program/degree",
      "names": ["Student Name 1", "Student Name 2", "Student Name 3", ...]
    }},
    {{
      "description": "Another department description",
      "names": ["Student Name 4", "Student Name 5", ...]
    }}
  ]
}}

Rules:
1. Extract ONLY graduate names (not faculty, speakers, staff, or performers)
2. Be comprehensive - capture ALL groups and ALL names within each group
3. Preserve exact name spelling from transcript
4. Keep the full description text as it appears
5. If you see a pattern of names without a clear description, create a generic description like "Graduates" or use the last known department
6. Include every single name mentioned - this is critical!

Example output:
{{
  "groups": [
    {{
      "description": "In the School of Engineering, Department of Mechanical Engineering, Master of Science in Mechanical Engineering",
      "names": ["John Smith", "Jane Doe", "Bob Johnson"]
    }},
    {{
      "description": "Doctor of Philosophy",
      "names": ["Alice Williams", "Charlie Brown"]
    }}
  ]
}}"""
                },
                {
                    "role": "user",
                    "content": f"Extract ALL graduate groups and names from this {school} {year} commencement transcript:\n\n{transcript_text}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        # Parse response
        result_text = response.choices[0].message.content
        data = json.loads(result_text)
        
        return data.get("groups", [])
        
    except Exception as e:
        print(f"\n❌ Error using GPT: {e}")
        raise


def parse_description(description):
    """
    Parse department description to extract structured info
    
    Args:
        description: Description string like "In the School of Engineering, Department of CS, Master of Science"
    
    Returns:
        Dictionary with parsed fields
    """
    
    # Extract basic info
    info = {
        "department": None,
        "program": None,
        "degree_type": None,
        "degree_level": None,
        "school_within": None
    }
    
    desc_lower = description.lower()
    
    # Extract school
    if "school of engineering" in desc_lower:
        info["school_within"] = "School of Engineering"
    elif "schwarzman college of computing" in desc_lower or "college of computing" in desc_lower:
        info["school_within"] = "Schwarzman College of Computing"
    elif "sloan school" in desc_lower:
        info["school_within"] = "Sloan School of Management"
    
    # Extract department
    if "department of" in desc_lower:
        start = description.lower().find("department of")
        rest = description[start + 13:]  # Skip "department of"
        # Find next comma or period
        end = len(rest)
        for char in [',', '.', '\n']:
            if char in rest:
                end = min(end, rest.find(char))
        info["department"] = rest[:end].strip()
    
    # Extract degree level and type
    if "doctor of philosophy" in desc_lower or "phd" in desc_lower:
        info["degree_level"] = "Doctoral"
        info["degree_type"] = "PhD"
    elif "doctor of science" in desc_lower or "scd" in desc_lower:
        info["degree_level"] = "Doctoral"
        info["degree_type"] = "ScD"
    elif "master of science" in desc_lower:
        info["degree_level"] = "Master's"
        info["degree_type"] = "MS"
    elif "master of engineering" in desc_lower:
        info["degree_level"] = "Master's"
        info["degree_type"] = "MEng"
    elif "master of business" in desc_lower or "mba" in desc_lower:
        info["degree_level"] = "Master's"
        info["degree_type"] = "MBA"
    elif "master" in desc_lower:
        info["degree_level"] = "Master's"
        info["degree_type"] = "Master's"
    elif "bachelor" in desc_lower:
        info["degree_level"] = "Bachelor's"
        info["degree_type"] = "Bachelor's"
    
    return info


def convert_groups_to_graduates(groups, school, year):
    """
    Convert groups format to structured graduates list
    
    Args:
        groups: List of {description, names} dicts
        school: School name
        year: Year
    
    Returns:
        Structured data with graduates list
    """
    
    graduates = []
    
    for group in groups:
        description = group.get("description", "")
        names = group.get("names", [])
        
        # Parse the description
        parsed = parse_description(description)
        
        # Create a graduate entry for each name
        for name in names:
            if name and name.strip():  # Skip empty names
                graduate = {
                    "name": name.strip(),
                    "department": parsed["department"] or "Unknown",
                    "program": parsed["program"],
                    "degree_type": parsed["degree_type"] or "Unknown",
                    "degree_level": parsed["degree_level"] or "Unknown",
                    "school_within": parsed["school_within"],
                    "description": description,
                    "notes": None
                }
                graduates.append(graduate)
    
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
    
    # Count by degree level
    degree_counts = {}
    for grad in graduates:
        level = grad.get('degree_level', 'Unknown')
        degree_counts[level] = degree_counts.get(level, 0) + 1
    
    if degree_counts:
        print("\n📊 By degree level:")
        for level, count in sorted(degree_counts.items()):
            print(f"  - {level}: {count}")
    
    # Show sample graduates
    print(f"\n👤 Sample graduates (first 10):")
    for i, grad in enumerate(graduates[:10], 1):
        dept = grad.get('department', 'Unknown')
        degree = grad.get('degree_type', '?')
        name = grad['name'][:35] + "..." if len(grad['name']) > 35 else grad['name']
        print(f"  {i:2d}. {name:<38} | {degree:6} | {dept}")
    
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

