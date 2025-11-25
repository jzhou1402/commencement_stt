#!/usr/bin/env python3
"""
Enrich Graduate Profiles

Uses OpenAI Responses API with GPT-5.1:
- High reasoning mode
- Web search enabled
- Free-form output with citations

Usage:
    python enrich_profiles.py <graduates_json_file> <name>
    python enrich_profiles.py <graduates_json_file> --sample N
    
Examples:
    # Process one specific person
    python enrich_profiles.py mit_2025_graduates.json "Jane Smith"
    
    # Process first N people
    python enrich_profiles.py mit_2025_graduates.json --sample 5
    
    # Process everyone
    python enrich_profiles.py mit_2025_graduates.json
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from openai import OpenAI


def enrich_graduate(graduate, school, year, client):
    """
    Research a single graduate using GPT-5.1 responses API with web search
    
    Args:
        graduate: Graduate dict with name, department, degree
        school: School name
        year: Graduation year
        client: OpenAI client
    
    Returns:
        Free-form profile with citations
    """
    
    name = graduate.get("name", "Unknown")
    department = graduate.get("department", "Unknown")
    degree = graduate.get("degree_type", "Unknown")
    
    print(f"\n   🔍 {name}")
    print(f"      {degree} - {department}")
    
    # Research prompt - framed as professional research, not surveillance
    prompt = f"""Research this graduate for professional networking and alumni relations purposes:

Name: {name}
Institution: {school} (Class of {year})
Department: {department}
Degree: {degree}

Find and compile:
- Academic background and research interests
- Professional experience and current position
- Publications and projects
- LinkedIn profile
- GitHub or other professional profiles
- Any public achievements or awards

Provide a comprehensive professional profile with citations."""
    
    try:
        # Use responses API with GPT-5.1, high reasoning, and web search
        response = client.responses.create(
            model="gpt-5.1",
            input=prompt,
            reasoning={"effort": "high"},  # Enable deep reasoning
            tools=[{"type": "web_search"}] # Enable web search
        )
        
        # Extract text from response output
        profile_text = ""
        reasoning_summary = []
        sources = []
        
        if isinstance(response.output, list):
            for item in response.output:
                # Extract reasoning summaries
                if hasattr(item, 'type') and item.type == 'reasoning':
                    if hasattr(item, 'summary') and item.summary:
                        reasoning_summary.extend(item.summary)
                
                # Extract message content
                if hasattr(item, 'type') and item.type == 'message':
                    if hasattr(item, 'content'):
                        for content_item in item.content:
                            if hasattr(content_item, 'text'):
                                profile_text += content_item.text
                            # Extract sources/citations from annotations
                            if hasattr(content_item, 'annotations'):
                                for annotation in content_item.annotations:
                                    if hasattr(annotation, 'text'):
                                        sources.append(str(annotation))
        else:
            profile_text = str(response.output)
        
        # Create profile object
        profile = {
            "name": name,
            "school": school,
            "year": year,
            "department": department,
            "degree": degree,
            "profile": profile_text.strip(),
            "researched_at": datetime.now().isoformat(),
            "model": "gpt-5.1",
            "prompt": prompt
        }
        
        # Add reasoning and sources if available
        if reasoning_summary:
            profile["reasoning_summary"] = reasoning_summary
        if sources:
            profile["sources"] = sources
        
        print(f"      ✓ Profile created")
        
        return profile
        
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return {
            "name": name,
            "error": str(e),
            "researched_at": datetime.now().isoformat()
        }


def main():
    print("=" * 80)
    print("ENRICH GRADUATE PROFILES")
    print("Using Responses API: GPT-5.1 + High Reasoning + Web Search")
    print("=" * 80)
    
    # Parse arguments
    if len(sys.argv) < 2:
        print("\n❌ Error: No graduates file provided")
        print("\nUsage:")
        print("  python enrich_profiles.py <graduates_json_file> <name>")
        print("  python enrich_profiles.py <graduates_json_file> --sample N")
        print("\nExamples:")
        print('  python enrich_profiles.py mit_2025_graduates.json "Jane Smith"')
        print("  python enrich_profiles.py mit_2025_graduates.json --sample 5")
        sys.exit(1)
    
    graduates_path = sys.argv[1]
    
    # Check for specific name or sample flag
    specific_name = None
    sample_size = None
    
    if len(sys.argv) >= 3:
        if sys.argv[2] == "--sample":
            try:
                sample_size = int(sys.argv[3])
            except (IndexError, ValueError):
                print("❌ Error: Invalid --sample argument")
                sys.exit(1)
        else:
            # Second argument is a name
            specific_name = sys.argv[2]
    
    # Check if file exists
    if not os.path.exists(graduates_path):
        print(f"\n❌ Error: File not found: {graduates_path}")
        sys.exit(1)
    
    # Get API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ Error: No OpenAI API key found!")
        print("Set OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    # Load graduates
    print(f"\n📖 Loading graduates: {graduates_path}")
    with open(graduates_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    school = data.get("school", "Unknown")
    year = data.get("year", "Unknown")
    graduates = data.get("graduates", [])
    
    print(f"✓ Loaded {len(graduates)} graduates from {school} {year}")
    
    # Filter by name if specified
    if specific_name:
        matching = [g for g in graduates if g.get("name", "").lower() == specific_name.lower()]
        if not matching:
            # Try partial match
            matching = [g for g in graduates if specific_name.lower() in g.get("name", "").lower()]
        
        if not matching:
            print(f"\n❌ Error: No graduate found matching '{specific_name}'")
            print("\nAvailable names (first 10):")
            for g in graduates[:10]:
                print(f"  - {g.get('name')}")
            sys.exit(1)
        
        if len(matching) > 1:
            print(f"\n⚠️  Found {len(matching)} matching graduates:")
            for i, g in enumerate(matching, 1):
                print(f"  {i}. {g.get('name')} - {g.get('department')}")
            print("\nUsing first match. For exact match, use full name.")
        
        graduates = [matching[0]]
        print(f"🎯 Processing: {graduates[0].get('name')}")
    
    elif sample_size:
        graduates = graduates[:sample_size]
        print(f"⚠️  Processing sample of {len(graduates)} graduates")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Enrich profiles
    print("\n" + "=" * 80)
    print("RESEARCHING GRADUATES")
    print("=" * 80)
    print(f"\nEstimated time: ~3-4 minutes per person")
    print(f"Total: ~{len(graduates) * 3.5:.1f} minutes\n")
    
    enriched_profiles = []
    
    for i, graduate in enumerate(graduates, 1):
        print(f"[{i}/{len(graduates)}]", end=" ")
        
        try:
            profile = enrich_graduate(graduate, school, year, client)
            enriched_profiles.append(profile)
            
            # Rate limiting
            if i < len(graduates):
                time.sleep(1.0)  # 1 second between requests
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            print(f"Processed {i-1}/{len(graduates)} graduates")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue
    
    # Display summary
    print("\n" + "=" * 80)
    print("ENRICHMENT COMPLETE")
    print("=" * 80)
    
    print(f"\n✓ Enriched {len(enriched_profiles)} profiles")
    
    # Count errors
    errors = sum(1 for p in enriched_profiles if "error" in p)
    if errors > 0:
        print(f"⚠️  {errors} profiles had errors")
    
    # Show sample
    print("\n📋 Sample profiles (first 2):")
    for i, profile in enumerate(enriched_profiles[:2], 1):
        print(f"\n{i}. {profile.get('name', 'Unknown')}")
        profile_text = profile.get('profile', 'No profile')
        # Show first 200 chars
        if len(profile_text) > 200:
            print(f"   {profile_text[:200]}...")
        else:
            print(f"   {profile_text}")
    
    # Save enriched profiles
    graduates_path = Path(graduates_path)
    output_filename = f"{school.lower()}_{year}_enriched.json"
    output_path = graduates_path.parent / output_filename
    
    output_data = {
        "school": school,
        "year": year,
        "enriched_at": datetime.now().isoformat(),
        "total_graduates": len(enriched_profiles),
        "graduates": enriched_profiles
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Saved enriched profiles to: {output_path}")
    
    print("\n" + "=" * 80)
    print("DONE! 🎉")
    print("=" * 80)


if __name__ == "__main__":
    main()
