#!/usr/bin/env python3
"""
Enrich chunks with contextual information before embedding.

Prepends structured context to each chunk:
- Race name and location
- Participant profile
- Preceding moderator question
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import DATA_DIR, CHUNKS_DIR, FOCUS_GROUPS_DIR


def load_focus_group_metadata(fg_id: str) -> Dict:
    """Load focus group metadata."""
    fg_file = FOCUS_GROUPS_DIR / f"{fg_id}.json"
    if not fg_file.exists():
        raise FileNotFoundError(f"Focus group metadata not found: {fg_file}")

    with open(fg_file) as f:
        return json.load(f)


def load_chunks(fg_id: str) -> List[Dict]:
    """Load all chunks for a focus group."""
    chunks_dir = CHUNKS_DIR / fg_id
    if not chunks_dir.exists():
        raise FileNotFoundError(f"Chunks directory not found: {chunks_dir}")

    chunks = []
    for chunk_file in sorted(chunks_dir.glob("*.json")):
        if chunk_file.name == "all_chunks.json":
            continue
        with open(chunk_file) as f:
            chunks.append(json.load(f))

    return chunks


def enrich_chunk(chunk: Dict, fg_metadata: Dict) -> Dict:
    """
    Enrich a single chunk with contextual information.

    Format:
    [Race Name | Location | Participant Profile]
    Q: Moderator question

    "Original content"
    """
    race_name = fg_metadata.get("race_name", "Unknown Race")
    location = fg_metadata.get("location", "Unknown Location")

    # Get participant profile
    participant = chunk.get("participant", "Unknown")
    participant_profile = chunk.get("participant_profile", "")

    # Get moderator question
    moderator_q = chunk.get("preceding_moderator_q", "")

    # Get original content
    content = chunk.get("content", "")

    # Build enriched content
    header = f"[{race_name} | {location} | {participant}: {participant_profile}]"

    enriched_parts = [header]
    if moderator_q:
        enriched_parts.append(f"Q: {moderator_q}")
    enriched_parts.append(f'"{content}"')

    enriched_content = "\n".join(enriched_parts)

    # Return new chunk with enriched content
    enriched_chunk = chunk.copy()
    enriched_chunk["content_original"] = content
    enriched_chunk["content"] = enriched_content

    return enriched_chunk


def enrich_focus_group(fg_id: str, output_dir: Optional[Path] = None) -> List[Dict]:
    """
    Enrich all chunks for a focus group.

    Args:
        fg_id: Focus group ID
        output_dir: Optional output directory for enriched chunks

    Returns:
        List of enriched chunk dicts
    """
    print(f"Enriching focus group: {fg_id}")

    # Load metadata and chunks
    fg_metadata = load_focus_group_metadata(fg_id)
    chunks = load_chunks(fg_id)

    print(f"  Loaded {len(chunks)} chunks")
    print(f"  Race: {fg_metadata.get('race_name')}")
    print(f"  Location: {fg_metadata.get('location')}")

    # Enrich each chunk
    enriched_chunks = []
    for chunk in chunks:
        enriched = enrich_chunk(chunk, fg_metadata)
        enriched_chunks.append(enriched)

    # Save if output directory specified
    if output_dir:
        fg_output_dir = output_dir / fg_id
        fg_output_dir.mkdir(parents=True, exist_ok=True)

        # Save individual chunks
        for i, chunk in enumerate(enriched_chunks, 1):
            chunk_file = fg_output_dir / f"{i:03d}.json"
            with open(chunk_file, "w") as f:
                json.dump(chunk, f, indent=2)

        # Save all chunks in one file
        all_chunks_file = fg_output_dir / "all_chunks.json"
        with open(all_chunks_file, "w") as f:
            json.dump(enriched_chunks, f, indent=2)

        print(f"  Saved to: {fg_output_dir}")

    return enriched_chunks


def main():
    """Enrich chunks for specified focus groups."""
    import argparse

    parser = argparse.ArgumentParser(description="Enrich chunks with context")
    parser.add_argument("focus_groups", nargs="*", help="Focus group IDs to enrich (default: all)")
    parser.add_argument("--output", type=str, default="data/chunks_enriched",
                        help="Output directory for enriched chunks")
    parser.add_argument("--preview", action="store_true", help="Preview first chunk only")

    args = parser.parse_args()

    output_dir = Path(args.output)

    # Get focus groups to process
    if args.focus_groups:
        fg_ids = args.focus_groups
    else:
        # All focus groups
        fg_ids = [d.name for d in CHUNKS_DIR.iterdir() if d.is_dir()]

    print(f"Processing {len(fg_ids)} focus group(s)")
    print(f"Output directory: {output_dir}")
    print()

    for fg_id in fg_ids:
        enriched = enrich_focus_group(
            fg_id,
            output_dir=None if args.preview else output_dir
        )

        if args.preview and enriched:
            print("\n--- PREVIEW (first chunk) ---")
            print(enriched[0]["content"])
            print("--- END PREVIEW ---\n")
            break

    if not args.preview:
        print(f"\nDone! Enriched chunks saved to: {output_dir}")


if __name__ == "__main__":
    main()
