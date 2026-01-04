#!/usr/bin/env python3
"""
Preprocessing script for strategy memos.
Converts markdown strategy memos into structured JSON chunks for retrieval.

Chunking strategy:
- Children: Subsection level (### headers) - granular retrieval
- Parents: Section level (## headers) with LLM summaries - routing/context
- Tables kept as single chunks
- Rich metadata from race metadata.json

Output:
- data/strategy_chunks/{race_id}/chunk-{NNN}.json
- data/strategy_chunks/hierarchical_parents.json
- data/strategy_chunks/manifest.json (with section_summaries)

Run: python scripts/preprocess_memos.py
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

# Paths
CORPUS_DIR = Path(__file__).parent.parent / "political-consulting-corpus"
DATA_DIR = Path(__file__).parent.parent / "data"
STRATEGY_CHUNKS_DIR = DATA_DIR / "strategy_chunks"


@dataclass
class StrategyMemoChunk:
    """A chunk from a strategy memo."""
    chunk_id: str
    race_id: str
    content: str
    section: str
    subsection: Optional[str]

    # From race metadata
    state: str
    year: int
    outcome: str
    margin: float
    office: str
    candidate_name: str
    opponent_name: str

    # Source tracking
    source_file: str
    line_number: int


@dataclass
class StrategyMemoMetadata:
    """Metadata for a strategy memo."""
    race_id: str
    state: str
    year: int
    outcome: str
    margin: float
    office: str
    candidate_name: str
    opponent_name: str
    sections: List[str]
    chunk_count: int
    source_file: str


@dataclass
class StrategyMemoParent:
    """Section-level parent for hierarchical retrieval."""
    id: str
    race_id: str
    section: str
    summary: str
    content: str
    chunk_count: int
    child_ids: List[str]
    outcome: str
    state: str
    year: int
    margin: float


def slugify(text: str) -> str:
    """Convert text to slug for IDs."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def generate_section_summary(section_name: str, section_content: str) -> str:
    """Generate LLM summary for a section using OpenRouter."""
    from eval.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, GEMINI_GENERATION_MODEL
    import openai

    client = openai.OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

    # Skip header sections - they're just metadata
    if section_name == "Header":
        return "Race metadata and basic information."

    response = client.chat.completions.create(
        model=GEMINI_GENERATION_MODEL,
        messages=[{
            "role": "user",
            "content": f"""Summarize this section from a political campaign strategy memo in 2-3 sentences.
Focus on: key lessons, what worked/failed, and actionable insights.
Keep it factual and specific - include names, numbers, and quotes where relevant.

Section: {section_name}
Content:
{section_content[:4000]}

Summary:"""
        }],
        max_tokens=200,
        temperature=0
    )
    return response.choices[0].message.content.strip()


def create_section_parents(
    all_chunks: Dict[str, List[StrategyMemoChunk]],
    generate_summaries: bool = True
) -> Tuple[List[StrategyMemoParent], Dict[str, Dict[str, str]]]:
    """
    Create section-level parents from chunks.

    Args:
        all_chunks: Dict mapping race_id -> list of chunks
        generate_summaries: Whether to generate LLM summaries

    Returns:
        Tuple of (list of parents, dict mapping race_id -> section_summaries)
    """
    all_parents = []
    section_summaries_by_race = {}

    for race_id, chunks in all_chunks.items():
        # Group chunks by section
        sections = defaultdict(list)
        for chunk in chunks:
            sections[chunk.section].append(chunk)

        section_summaries = {}

        for section_name, section_chunks in sections.items():
            # Combine all child content for summary
            section_content = "\n\n".join([c.content for c in section_chunks])

            # Generate or skip summary
            if generate_summaries:
                print(f"    Generating summary for: {section_name[:40]}...")
                summary = generate_section_summary(section_name, section_content)
            else:
                # Fallback: concatenate subsection titles
                subsections = [c.subsection for c in section_chunks if c.subsection]
                summary = f"Subsections: {', '.join(subsections)}" if subsections else section_content[:200]

            section_summaries[section_name] = summary

            # Get metadata from first chunk
            first_chunk = section_chunks[0]

            parent = StrategyMemoParent(
                id=f"parent-{race_id}-memo-{slugify(section_name)}",
                race_id=race_id,
                section=section_name,
                summary=summary,
                content=f"[{first_chunk.state} {first_chunk.year} | {first_chunk.outcome} | {first_chunk.margin:+.1f}%]\nSection: {section_name}\n\n{summary}",
                chunk_count=len(section_chunks),
                child_ids=[c.chunk_id for c in section_chunks],
                outcome=first_chunk.outcome,
                state=first_chunk.state,
                year=first_chunk.year,
                margin=first_chunk.margin
            )
            all_parents.append(parent)

        section_summaries_by_race[race_id] = section_summaries

    return all_parents, section_summaries_by_race


def load_race_metadata(race_dir: Path) -> Dict:
    """Load race metadata from metadata.json."""
    metadata_file = race_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            return json.load(f)

    # Fallback: infer from directory name
    dir_name = race_dir.name
    parts = dir_name.split("-")
    return {
        "race_id": f"{parts[0]}-{parts[1]}" if len(parts) > 1 else dir_name,
        "state": parts[2].title() if len(parts) > 2 else "Unknown",
        "office": parts[3].title() if len(parts) > 3 else "Unknown",
        "year": int(parts[4]) if len(parts) > 4 else 0,
        "outcome": "unknown",
        "margin": 0.0,
        "our_candidate": {"name": "Unknown"},
        "opponent": {"name": "Unknown"}
    }


def parse_memo_structure(lines: List[str]) -> List[Tuple[int, str, str, Optional[str], str]]:
    """
    Parse strategy memo into chunks based on section/subsection structure.

    Returns list of:
        (line_number, section, subsection, content)

    Chunking rules:
    1. Each ### subsection becomes a chunk
    2. Content between ## and first ### (if any) becomes a chunk
    3. Sections without ### subsections become single chunks
    4. Tables are kept together with preceding text
    """
    chunks = []
    current_section = "Header"
    current_subsection = None
    current_content = []
    chunk_start_line = 1

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check for section header (##)
        if stripped.startswith("## ") and not stripped.startswith("### "):
            # Save previous chunk if has content
            if current_content:
                content_text = "\n".join(current_content).strip()
                if content_text and not _is_only_separator(content_text):
                    chunks.append((
                        chunk_start_line,
                        current_section,
                        current_subsection,
                        content_text
                    ))

            # Start new section
            current_section = stripped[3:].strip()
            current_subsection = None
            current_content = []
            chunk_start_line = i + 1
            i += 1
            continue

        # Check for subsection header (###)
        if stripped.startswith("### "):
            # Save previous chunk if has content
            if current_content:
                content_text = "\n".join(current_content).strip()
                if content_text and not _is_only_separator(content_text):
                    chunks.append((
                        chunk_start_line,
                        current_section,
                        current_subsection,
                        content_text
                    ))

            # Start new subsection
            current_subsection = stripped[4:].strip()
            current_content = []
            chunk_start_line = i + 1
            i += 1
            continue

        # Check for table - keep table together
        if stripped.startswith("|") and "---" not in stripped:
            # Collect entire table
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            current_content.extend(table_lines)
            continue

        # Regular content
        current_content.append(line)
        i += 1

    # Don't forget the last chunk
    if current_content:
        content_text = "\n".join(current_content).strip()
        if content_text and not _is_only_separator(content_text):
            chunks.append((
                chunk_start_line,
                current_section,
                current_subsection,
                content_text
            ))

    return chunks


def _is_only_separator(text: str) -> bool:
    """Check if text is only separators (---)."""
    return all(c in "-\n " for c in text)


def extract_header_metadata(lines: List[str]) -> Dict[str, str]:
    """Extract metadata from memo header (Race, Candidate, Outcome, etc.)."""
    header = {}
    for line in lines[:15]:  # Header is in first 15 lines
        if line.startswith("**Race:**"):
            header["race_title"] = line.replace("**Race:**", "").strip()
        elif line.startswith("**Candidate:**"):
            header["candidate"] = line.replace("**Candidate:**", "").strip()
        elif line.startswith("**Opponent:**"):
            header["opponent"] = line.replace("**Opponent:**", "").strip()
        elif line.startswith("**Outcome:**"):
            outcome_str = line.replace("**Outcome:**", "").strip()
            header["outcome_str"] = outcome_str
    return header


def process_strategy_memo(memo_path: Path) -> Tuple[List[StrategyMemoChunk], StrategyMemoMetadata]:
    """Process a single strategy memo into chunks."""

    # Get race directory and metadata
    race_dir = memo_path.parent
    race_meta = load_race_metadata(race_dir)

    # Extract race_id from directory name
    dir_name = race_dir.name
    race_id = "-".join(dir_name.split("-")[:2])  # e.g., "race-007"

    # Read memo
    with open(memo_path, 'r') as f:
        content = f.read()
    lines = content.split('\n')

    # Extract header metadata (for validation)
    header_meta = extract_header_metadata(lines)

    # Parse into chunks
    raw_chunks = parse_memo_structure(lines)

    # Get metadata values
    state = race_meta.get("state", "Unknown")
    year = race_meta.get("year", 0)
    outcome = race_meta.get("outcome", "unknown")
    margin = race_meta.get("margin", 0.0)
    office = race_meta.get("office", "Unknown")

    candidate_info = race_meta.get("our_candidate", {})
    candidate_name = candidate_info.get("name", "Unknown")

    opponent_info = race_meta.get("opponent", {})
    opponent_name = opponent_info.get("name", "Unknown")

    # Relative path for source tracking
    source_file = str(memo_path.relative_to(CORPUS_DIR.parent))

    # Create chunk objects
    chunks = []
    sections_seen = set()

    for i, (line_num, section, subsection, chunk_content) in enumerate(raw_chunks):
        sections_seen.add(section)

        chunk = StrategyMemoChunk(
            chunk_id=f"{race_id}-memo-chunk-{i+1:03d}",
            race_id=race_id,
            content=chunk_content,
            section=section,
            subsection=subsection,
            state=state,
            year=year,
            outcome=outcome,
            margin=margin,
            office=office,
            candidate_name=candidate_name,
            opponent_name=opponent_name,
            source_file=source_file,
            line_number=line_num
        )
        chunks.append(chunk)

    # Create metadata
    metadata = StrategyMemoMetadata(
        race_id=race_id,
        state=state,
        year=year,
        outcome=outcome,
        margin=margin,
        office=office,
        candidate_name=candidate_name,
        opponent_name=opponent_name,
        sections=sorted(list(sections_seen)),
        chunk_count=len(chunks),
        source_file=source_file
    )

    return chunks, metadata


def save_chunks(chunks: List[StrategyMemoChunk], race_id: str):
    """Save chunks to JSON files."""
    chunk_dir = STRATEGY_CHUNKS_DIR / race_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    # Save individual chunks
    for chunk in chunks:
        chunk_num = chunk.chunk_id.split("-")[-1]
        chunk_file = chunk_dir / f"chunk-{chunk_num}.json"
        with open(chunk_file, 'w') as f:
            json.dump(asdict(chunk), f, indent=2)

    # Save all chunks in one file
    all_chunks_file = chunk_dir / "all_chunks.json"
    with open(all_chunks_file, 'w') as f:
        json.dump([asdict(c) for c in chunks], f, indent=2)


def save_metadata(metadata: StrategyMemoMetadata):
    """Save strategy memo metadata."""
    metadata_dir = STRATEGY_CHUNKS_DIR / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    metadata_file = metadata_dir / f"{metadata.race_id}.json"
    with open(metadata_file, 'w') as f:
        json.dump(asdict(metadata), f, indent=2)


def main():
    """Process all strategy memos."""
    import argparse

    parser = argparse.ArgumentParser(description="Preprocess strategy memos")
    parser.add_argument("--skip-summaries", action="store_true",
                        help="Skip LLM summary generation (use concatenated titles)")
    parser.add_argument("--parents-only", action="store_true",
                        help="Only generate parents (assumes chunks already exist)")
    args = parser.parse_args()

    print("=" * 60)
    print("Strategy Memo Preprocessing")
    print("=" * 60)

    # Find all strategy memos
    memos = list(CORPUS_DIR.glob("races/*/strategy-memo.md"))
    print(f"\nFound {len(memos)} strategy memos")

    manifest = {
        "total_memos": 0,
        "total_chunks": 0,
        "total_parents": 0,
        "by_outcome": {"win": 0, "loss": 0, "unknown": 0},
        "memos": []
    }

    # Collect all chunks by race_id for parent generation
    all_chunks_by_race: Dict[str, List[StrategyMemoChunk]] = {}

    # Phase 1: Process chunks (unless --parents-only)
    if not args.parents_only:
        print("\n" + "-" * 40)
        print("Phase 1: Extracting chunks")
        print("-" * 40)

        for memo_path in sorted(memos):
            print(f"\nProcessing: {memo_path.parent.name}/strategy-memo.md")

            try:
                chunks, metadata = process_strategy_memo(memo_path)

                # Save outputs
                save_chunks(chunks, metadata.race_id)
                save_metadata(metadata)

                # Collect for parent generation
                all_chunks_by_race[metadata.race_id] = chunks

                # Update manifest (will add section_summaries later)
                manifest["total_memos"] += 1
                manifest["total_chunks"] += len(chunks)
                manifest["by_outcome"][metadata.outcome] = manifest["by_outcome"].get(metadata.outcome, 0) + 1

                manifest["memos"].append({
                    "race_id": metadata.race_id,
                    "state": metadata.state,
                    "year": metadata.year,
                    "outcome": metadata.outcome,
                    "margin": metadata.margin,
                    "office": metadata.office,
                    "chunk_count": metadata.chunk_count,
                    "sections": metadata.sections,
                    "section_summaries": {}  # Will be filled in Phase 2
                })

                print(f"  ✓ {len(chunks)} chunks extracted")

            except Exception as e:
                print(f"  ✗ Error: {e}")
                import traceback
                traceback.print_exc()
    else:
        # Load existing chunks
        print("\nLoading existing chunks...")
        for race_dir in sorted(STRATEGY_CHUNKS_DIR.iterdir()):
            if race_dir.is_dir() and race_dir.name.startswith("race-"):
                chunks_file = race_dir / "all_chunks.json"
                if chunks_file.exists():
                    with open(chunks_file) as f:
                        chunk_dicts = json.load(f)
                        chunks = [StrategyMemoChunk(**c) for c in chunk_dicts]
                        all_chunks_by_race[race_dir.name] = chunks
                        print(f"  Loaded {len(chunks)} chunks from {race_dir.name}")

        # Load existing manifest
        manifest_file = STRATEGY_CHUNKS_DIR / "manifest.json"
        if manifest_file.exists():
            with open(manifest_file) as f:
                manifest = json.load(f)

    # Phase 2: Generate parents with LLM summaries
    print("\n" + "-" * 40)
    print("Phase 2: Generating section parents")
    print("-" * 40)

    generate_summaries = not args.skip_summaries
    if generate_summaries:
        print("Using LLM to generate section summaries...")
    else:
        print("Using concatenated subsection titles (--skip-summaries)")

    parents, section_summaries_by_race = create_section_parents(
        all_chunks_by_race,
        generate_summaries=generate_summaries
    )

    # Update manifest with section_summaries
    for memo_entry in manifest["memos"]:
        race_id = memo_entry["race_id"]
        if race_id in section_summaries_by_race:
            memo_entry["section_summaries"] = section_summaries_by_race[race_id]

    manifest["total_parents"] = len(parents)

    # Save parents
    parents_file = STRATEGY_CHUNKS_DIR / "hierarchical_parents.json"
    with open(parents_file, 'w') as f:
        json.dump([asdict(p) for p in parents], f, indent=2)
    print(f"\n  ✓ {len(parents)} parents saved to {parents_file}")

    # Save manifest
    manifest_file = STRATEGY_CHUNKS_DIR / "manifest.json"
    STRATEGY_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Strategy memos processed: {manifest['total_memos']}")
    print(f"Total chunks (children): {manifest['total_chunks']}")
    print(f"Total parents: {manifest['total_parents']}")
    print(f"By outcome: {manifest['by_outcome']}")
    print(f"Output directory: {STRATEGY_CHUNKS_DIR}")
    print(f"Parents saved: {parents_file}")
    print(f"Manifest saved: {manifest_file}")


if __name__ == "__main__":
    main()
