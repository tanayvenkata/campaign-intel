#!/usr/bin/env python3
"""
Preprocessing script for focus group corpus.
Converts markdown transcripts into structured JSON for retrieval.

Output:
- data/chunks/{focus_group_id}/chunk-{NNN}.json - Dialogue chunks (searchable)
- data/focus-groups/{focus_group_id}.json - Focus group metadata (context)
- data/manifest.json - Index of all focus groups
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Paths
CORPUS_DIR = Path(__file__).parent.parent / "political-consulting-corpus"
DATA_DIR = Path(__file__).parent.parent / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
FOCUS_GROUPS_DIR = DATA_DIR / "focus-groups"


@dataclass
class Chunk:
    chunk_id: str
    focus_group_id: str
    content: str
    participant: str
    participant_profile: str
    section: str
    preceding_moderator_q: Optional[str]
    source_file: str
    line_number: int


@dataclass
class FocusGroupMetadata:
    focus_group_id: str
    race_id: str
    race_name: str
    outcome: str
    location: str
    date: str
    moderator: str
    participant_count: int
    participant_summary: str
    participants: Dict[str, str]
    moderator_notes: Dict
    source_file: str


def extract_header(lines: List[str]) -> Dict[str, str]:
    """Extract header metadata from the transcript."""
    header = {}
    for line in lines[:20]:  # Header is in first 20 lines
        if line.startswith("**Race:**"):
            header["race"] = line.replace("**Race:**", "").strip()
        elif line.startswith("**Location:**"):
            header["location"] = line.replace("**Location:**", "").strip()
        elif line.startswith("**Date:**"):
            header["date"] = line.replace("**Date:**", "").strip()
        elif line.startswith("**Moderator:**"):
            header["moderator"] = line.replace("**Moderator:**", "").strip()
        elif line.startswith("**Participants:**"):
            header["participants_summary"] = line.replace("**Participants:**", "").strip()
    return header


def extract_participant_profiles(lines: List[str]) -> Dict[str, str]:
    """Extract participant profiles (P1-P10)."""
    profiles = {}
    in_profiles = False

    for line in lines:
        if "## Participant Profiles" in line:
            in_profiles = True
            continue
        if in_profiles and line.startswith("---"):
            break
        if in_profiles and line.startswith("- **P"):
            # Parse: - **P1 (M, 58):** Description
            match = re.match(r'- \*\*(P\d+)\s*\(([^)]+)\):\*\*\s*(.*)', line)
            if match:
                participant_id = match.group(1)
                demographics = match.group(2)
                description = match.group(3)
                profiles[participant_id] = f"{demographics}, {description}"

    return profiles


def extract_dialogue_and_sections(lines: List[str]) -> List[Tuple[int, str, str, str, Optional[str]]]:
    """
    Extract dialogue with section context.
    Returns: [(line_number, participant, content, section, preceding_moderator_q)]
    """
    dialogue = []
    current_section = "Unknown"
    last_moderator_q = None
    in_discussion = False
    in_moderator_notes = False

    for i, line in enumerate(lines):
        # Track when we enter discussion
        if "## Discussion" in line:
            in_discussion = True
            continue

        # Track when we enter moderator notes (stop parsing dialogue)
        if "## Moderator Notes" in line:
            in_moderator_notes = True
            continue

        if in_moderator_notes:
            continue

        if not in_discussion:
            continue

        # Track section changes
        if line.startswith("### "):
            # Extract section title (remove timestamp)
            section_match = re.match(r'### (.+?)(?:\s*\(\d+:\d+.*\))?$', line)
            if section_match:
                current_section = section_match.group(1).strip()
            continue

        # Track moderator questions
        if line.startswith("**MODERATOR:**"):
            last_moderator_q = line.replace("**MODERATOR:**", "").strip()
            continue

        # Extract participant dialogue
        participant_match = re.match(r'\*\*(P\d+):\*\*\s*(.*)', line)
        if participant_match:
            participant = participant_match.group(1)
            content = participant_match.group(2).strip()
            if content:  # Only add non-empty content
                dialogue.append((
                    i + 1,  # 1-indexed line number
                    participant,
                    content,
                    current_section,
                    last_moderator_q
                ))

    return dialogue


def extract_moderator_notes(lines: List[str]) -> Dict:
    """Extract moderator notes section."""
    notes = {
        "key_themes": [],
        "vote_intent_summary": "",
        "key_quotes": [],
        "full_text": ""
    }

    in_notes = False
    notes_lines = []

    for line in lines:
        if "## Moderator Notes" in line:
            in_notes = True
            continue
        if in_notes:
            notes_lines.append(line)

    notes["full_text"] = "\n".join(notes_lines)

    # Extract key themes
    for line in notes_lines:
        if "Key Themes" in line or "key themes" in line.lower():
            continue
        # Look for numbered themes
        theme_match = re.match(r'\d+\.\s*\*\*(.+?)\*\*', line)
        if theme_match:
            notes["key_themes"].append(theme_match.group(1))

    # Extract vote intent
    for line in notes_lines:
        if "Vote Intent" in line or "vote intent" in line.lower():
            # Look for the summary line after
            continue
        if "Brennan:" in line or "Schroeder:" in line or "Holloway:" in line:
            notes["vote_intent_summary"] = line.strip().lstrip("- ")
            break

    # Extract key quotes
    for line in notes_lines:
        if line.startswith("> "):
            quote = line.lstrip("> ").strip()
            if quote:
                notes["key_quotes"].append(quote)

    return notes


def get_race_metadata(race_dir: Path) -> Dict:
    """Get race metadata from metadata.json or infer from directory name."""
    metadata_file = race_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            return json.load(f)

    # Infer from directory name: race-007-ohio-senate-2024
    dir_name = race_dir.name
    parts = dir_name.split("-")
    return {
        "race_id": f"{parts[0]}-{parts[1]}",
        "state": parts[2].title() if len(parts) > 2 else "Unknown",
        "office": parts[3].title() if len(parts) > 3 else "Unknown",
        "year": int(parts[4]) if len(parts) > 4 else 0,
        "outcome": "unknown"
    }


def process_focus_group(transcript_path: Path) -> Tuple[List[Chunk], FocusGroupMetadata]:
    """Process a single focus group transcript."""

    with open(transcript_path, 'r') as f:
        content = f.read()
    lines = content.split('\n')

    # Extract focus group ID from path
    # e.g., race-007-ohio-senate-2024/focus-groups/fg-003-youngstown-working-class.md
    race_dir = transcript_path.parent.parent
    race_id = race_dir.name.split("-")[0] + "-" + race_dir.name.split("-")[1]  # race-007
    fg_name = transcript_path.stem  # fg-003-youngstown-working-class
    focus_group_id = f"{race_id}-{fg_name}"

    # Get race metadata
    race_meta = get_race_metadata(race_dir)

    # Extract components
    header = extract_header(lines)
    profiles = extract_participant_profiles(lines)
    dialogue = extract_dialogue_and_sections(lines)
    mod_notes = extract_moderator_notes(lines)

    # Relative path for source_file
    source_file = str(transcript_path.relative_to(CORPUS_DIR.parent))

    # Create chunks
    chunks = []
    for i, (line_num, participant, content, section, mod_q) in enumerate(dialogue):
        chunk = Chunk(
            chunk_id=f"{focus_group_id}-chunk-{i+1:03d}",
            focus_group_id=focus_group_id,
            content=content,
            participant=participant,
            participant_profile=profiles.get(participant, "Unknown"),
            section=section,
            preceding_moderator_q=mod_q,
            source_file=source_file,
            line_number=line_num
        )
        chunks.append(chunk)

    # Create metadata
    metadata = FocusGroupMetadata(
        focus_group_id=focus_group_id,
        race_id=race_id,
        race_name=header.get("race", race_meta.get("state", "Unknown")),
        outcome=race_meta.get("outcome", "unknown"),
        location=header.get("location", "Unknown"),
        date=header.get("date", "Unknown"),
        moderator=header.get("moderator", "Unknown"),
        participant_count=len(profiles),
        participant_summary=header.get("participants_summary", ""),
        participants=profiles,
        moderator_notes=mod_notes,
        source_file=source_file
    )

    return chunks, metadata


def save_chunks(chunks: List[Chunk], focus_group_id: str):
    """Save chunks to JSON files."""
    chunk_dir = CHUNKS_DIR / focus_group_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    for chunk in chunks:
        chunk_file = chunk_dir / f"{chunk.chunk_id.split('-')[-1]}.json"
        with open(chunk_file, 'w') as f:
            json.dump(asdict(chunk), f, indent=2)

    # Also save all chunks in one file for convenience
    all_chunks_file = chunk_dir / "all_chunks.json"
    with open(all_chunks_file, 'w') as f:
        json.dump([asdict(c) for c in chunks], f, indent=2)


def save_metadata(metadata: FocusGroupMetadata):
    """Save focus group metadata to JSON."""
    FOCUS_GROUPS_DIR.mkdir(parents=True, exist_ok=True)
    metadata_file = FOCUS_GROUPS_DIR / f"{metadata.focus_group_id}.json"
    with open(metadata_file, 'w') as f:
        json.dump(asdict(metadata), f, indent=2)


def main():
    """Process all focus group transcripts."""
    print("=" * 60)
    print("Focus Group Corpus Preprocessing")
    print("=" * 60)

    # Find all focus group transcripts
    transcripts = list(CORPUS_DIR.glob("races/*/focus-groups/*.md"))
    print(f"\nFound {len(transcripts)} focus group transcripts")

    manifest = {
        "total_focus_groups": 0,
        "total_chunks": 0,
        "focus_groups": []
    }

    for transcript_path in sorted(transcripts):
        print(f"\nProcessing: {transcript_path.name}")

        try:
            chunks, metadata = process_focus_group(transcript_path)

            # Save outputs
            save_chunks(chunks, metadata.focus_group_id)
            save_metadata(metadata)

            # Update manifest
            manifest["total_focus_groups"] += 1
            manifest["total_chunks"] += len(chunks)
            manifest["focus_groups"].append({
                "focus_group_id": metadata.focus_group_id,
                "race_name": metadata.race_name,
                "location": metadata.location,
                "chunk_count": len(chunks),
                "outcome": metadata.outcome
            })

            print(f"  ✓ {len(chunks)} chunks extracted")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()

    # Save manifest
    manifest_file = DATA_DIR / "manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Focus groups processed: {manifest['total_focus_groups']}")
    print(f"Total chunks created: {manifest['total_chunks']}")
    print(f"Output directory: {DATA_DIR}")
    print(f"Manifest saved: {manifest_file}")


if __name__ == "__main__":
    main()
