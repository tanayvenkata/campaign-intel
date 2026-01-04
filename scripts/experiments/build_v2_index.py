#!/usr/bin/env python3
"""
Build V2 index: Hierarchical + BGE-base local embeddings.

Usage:
    python scripts/build_v2_index.py --all           # Do everything
    python scripts/build_v2_index.py --parents       # Generate parent summaries only
    python scripts/build_v2_index.py --children      # Enrich children only
    python scripts/build_v2_index.py --embed         # Embed and upload only
"""

import json
import sys
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import (
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    DATA_DIR,
    CHUNKS_DIR,
    FOCUS_GROUPS_DIR,
    OPENAI_GENERATION_MODEL,
)

# Constants
INDEX_NAME = "focus-group-v2"
DIMENSION = 768
ENRICHED_DIR = DATA_DIR / "chunks_enriched"
PARENTS_FILE = DATA_DIR / "hierarchical_parents.json"


def load_focus_group_metadata(fg_id: str) -> Dict:
    """Load focus group metadata."""
    fg_file = FOCUS_GROUPS_DIR / f"{fg_id}.json"
    with open(fg_file) as f:
        return json.load(f)


def load_chunks_by_section(fg_id: str) -> Dict[str, List[Dict]]:
    """Load chunks grouped by section."""
    chunks_dir = CHUNKS_DIR / fg_id
    sections = defaultdict(list)

    for chunk_file in sorted(chunks_dir.glob("*.json")):
        if chunk_file.name == "all_chunks.json":
            continue
        with open(chunk_file) as f:
            chunk = json.load(f)
            sections[chunk.get("section", "Unknown")].append(chunk)

    return dict(sections)


def generate_all_parents(verbose: bool = True) -> List[Dict]:
    """Generate parent summaries for all focus groups using LLM."""
    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    all_parents = []
    fg_ids = sorted([d.name for d in CHUNKS_DIR.iterdir() if d.is_dir()])

    if verbose:
        print(f"Generating parents for {len(fg_ids)} focus groups...")

    for fg_idx, fg_id in enumerate(fg_ids):
        fg_meta = load_focus_group_metadata(fg_id)
        sections = load_chunks_by_section(fg_id)

        if verbose:
            print(f"  [{fg_idx+1}/{len(fg_ids)}] {fg_id} ({len(sections)} sections)")

        for section_name, chunks in sections.items():
            # Build utterances text
            utterances = [f"{c['participant']}: {c['content']}" for c in chunks]
            all_text = "\n".join(utterances)

            # Generate summary
            prompt = f"""Summarize this focus group discussion section in 2-3 sentences.
Focus on: key themes, voter sentiments, and any notable quotes.

Section: {section_name}
Focus Group: {fg_meta['race_name']} - {fg_meta['location']}

Discussion:
{all_text[:3500]}

Summary:"""

            response = client.chat.completions.create(
            response = client.chat.completions.create(
                model=OPENAI_GENERATION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )
            summary = response.choices[0].message.content.strip()

            # Build parent content for embedding
            parent_content = f"""[{fg_meta['race_name']} | {fg_meta['location']}]
Section: {section_name}

{summary}"""

            parent = {
                "id": f"parent-{fg_id}-{len(all_parents):04d}",
                "focus_group_id": fg_id,
                "section": section_name,
                "summary": summary,
                "content": parent_content,
                "chunk_count": len(chunks),
                "child_ids": [c["chunk_id"] for c in chunks],
            }
            all_parents.append(parent)

        time.sleep(0.3)  # Rate limiting

    # Save parents
    with open(PARENTS_FILE, "w") as f:
        json.dump(all_parents, f, indent=2)

    if verbose:
        print(f"\nSaved {len(all_parents)} parents to {PARENTS_FILE}")

    return all_parents


def enrich_all_children(verbose: bool = True) -> List[Dict]:
    """Enrich all chunks with context."""
    all_enriched = []
    fg_ids = sorted([d.name for d in CHUNKS_DIR.iterdir() if d.is_dir()])

    if verbose:
        print(f"Enriching children for {len(fg_ids)} focus groups...")

    for fg_idx, fg_id in enumerate(fg_ids):
        fg_meta = load_focus_group_metadata(fg_id)
        chunks_dir = CHUNKS_DIR / fg_id

        chunks = []
        for chunk_file in sorted(chunks_dir.glob("*.json")):
            if chunk_file.name == "all_chunks.json":
                continue
            with open(chunk_file) as f:
                chunks.append(json.load(f))

        enriched_chunks = []
        for chunk in chunks:
            # Build enriched content
            header = f"[{fg_meta['race_name']} | {fg_meta['location']} | {chunk['participant']}: {chunk.get('participant_profile', '')}]"
            moderator_q = chunk.get("preceding_moderator_q", "")
            content = chunk.get("content", "")

            enriched_parts = [header]
            if moderator_q:
                enriched_parts.append(f"Q: {moderator_q}")
            enriched_parts.append(f'"{content}"')

            enriched_content = "\n".join(enriched_parts)

            enriched_chunk = chunk.copy()
            enriched_chunk["content_original"] = content
            enriched_chunk["content"] = enriched_content
            enriched_chunks.append(enriched_chunk)

        all_enriched.extend(enriched_chunks)

        # Save to enriched directory
        fg_output_dir = ENRICHED_DIR / fg_id
        fg_output_dir.mkdir(parents=True, exist_ok=True)

        all_chunks_file = fg_output_dir / "all_chunks.json"
        with open(all_chunks_file, "w") as f:
            json.dump(enriched_chunks, f, indent=2)

        if verbose:
            print(f"  [{fg_idx+1}/{len(fg_ids)}] {fg_id}: {len(enriched_chunks)} chunks")

    if verbose:
        print(f"\nEnriched {len(all_enriched)} total chunks")

    return all_enriched


def embed_and_upload(verbose: bool = True):
    """Embed with BGE-base and upload to Pinecone."""
    from sentence_transformers import SentenceTransformer
    from pinecone import Pinecone, ServerlessSpec

    # Load model
    if verbose:
        print("Loading BGE-base model...")
    model = SentenceTransformer('BAAI/bge-base-en-v1.5')

    # Initialize Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Create index if needed
    existing = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        if verbose:
            print(f"Creating index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(10)  # Wait for index
    else:
        if verbose:
            print(f"Index '{INDEX_NAME}' exists, clearing...")
        index = pc.Index(INDEX_NAME)
        index.delete(delete_all=True)
        time.sleep(2)

    index = pc.Index(INDEX_NAME)

    # Load parents
    if verbose:
        print("\nLoading parents...")
    with open(PARENTS_FILE) as f:
        parents = json.load(f)

    # Load children
    if verbose:
        print("Loading enriched children...")
    all_children = []
    for fg_dir in sorted(ENRICHED_DIR.iterdir()):
        if not fg_dir.is_dir():
            continue
        all_chunks_file = fg_dir / "all_chunks.json"
        if all_chunks_file.exists():
            with open(all_chunks_file) as f:
                all_children.extend(json.load(f))

    if verbose:
        print(f"  Parents: {len(parents)}")
        print(f"  Children: {len(all_children)}")

    # Embed parents
    if verbose:
        print("\nEmbedding parents...")
    parent_texts = [p["content"] for p in parents]
    parent_embeddings = model.encode(parent_texts, show_progress_bar=verbose)

    # Embed children in batches
    if verbose:
        print("\nEmbedding children...")
    child_texts = [c["content"] for c in all_children]
    child_embeddings = model.encode(child_texts, show_progress_bar=verbose, batch_size=64)

    # Upload parents
    if verbose:
        print("\nUploading parents...")
    parent_vectors = []
    for p, emb in zip(parents, parent_embeddings):
        parent_vectors.append({
            "id": p["id"],
            "values": emb.tolist(),
            "metadata": {
                "type": "parent",
                "focus_group_id": p["focus_group_id"],
                "section": p["section"],
                "content": p["content"][:1000],
                "chunk_count": p["chunk_count"],
                "child_ids": json.dumps(p["child_ids"]),
            }
        })

    for i in range(0, len(parent_vectors), 100):
        batch = parent_vectors[i:i + 100]
        index.upsert(vectors=batch)

    # Upload children
    if verbose:
        print("Uploading children...")
    child_vectors = []
    for c, emb in zip(all_children, child_embeddings):
        child_vectors.append({
            "id": c["chunk_id"],
            "values": emb.tolist(),
            "metadata": {
                "type": "child",
                "focus_group_id": c["focus_group_id"],
                "participant": c["participant"],
                "participant_profile": c.get("participant_profile", "")[:200],
                "section": c.get("section", ""),
                "content": c["content"][:1000],
                "content_original": c.get("content_original", "")[:500],
                "source_file": c.get("source_file", ""),
                "line_number": c.get("line_number", 0),
            }
        })

    for i in range(0, len(child_vectors), 100):
        batch = child_vectors[i:i + 100]
        index.upsert(vectors=batch)
        if verbose and i % 500 == 0:
            print(f"  Uploaded {i + len(batch)}/{len(child_vectors)} children")

    # Verify
    time.sleep(3)
    stats = index.describe_index_stats()
    if verbose:
        print(f"\nIndex stats: {stats.total_vector_count} vectors")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build V2 hierarchical index")
    parser.add_argument("--all", action="store_true", help="Do everything")
    parser.add_argument("--parents", action="store_true", help="Generate parent summaries")
    parser.add_argument("--children", action="store_true", help="Enrich children")
    parser.add_argument("--embed", action="store_true", help="Embed and upload")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()
    verbose = not args.quiet

    if args.all or args.parents:
        print("=" * 60)
        print("STEP 1: Generating parent summaries")
        print("=" * 60)
        generate_all_parents(verbose)

    if args.all or args.children:
        print("\n" + "=" * 60)
        print("STEP 2: Enriching children")
        print("=" * 60)
        enrich_all_children(verbose)

    if args.all or args.embed:
        print("\n" + "=" * 60)
        print("STEP 3: Embedding and uploading")
        print("=" * 60)
        embed_and_upload(verbose)

    if not any([args.all, args.parents, args.children, args.embed]):
        parser.print_help()

    print("\nDone!")


if __name__ == "__main__":
    main()
