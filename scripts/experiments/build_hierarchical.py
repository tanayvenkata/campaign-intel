#!/usr/bin/env python3
"""
Build hierarchical index: parent summaries + enriched children.

Usage:
    python scripts/build_hierarchical.py --generate-parents  # Generate parent summaries
    python scripts/build_hierarchical.py --enrich-children   # Enrich all children
    python scripts/build_hierarchical.py --embed             # Embed to Pinecone
    python scripts/build_hierarchical.py --all               # Do everything
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
    EMBEDDING_MODEL,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    DATA_DIR,
    CHUNKS_DIR,
    FOCUS_GROUPS_DIR,
    OPENAI_GENERATION_MODEL,
)

import openai
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder

# Output paths
ENRICHED_DIR = DATA_DIR / "chunks_enriched"
PARENTS_FILE = DATA_DIR / "hierarchical_parents.json"

# Pinecone namespace
NAMESPACE = "hierarchical-v1"


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


def generate_parent_summary(
    section_name: str,
    chunks: List[Dict],
    fg_meta: Dict,
    client: openai.OpenAI
) -> str:
    """Generate LLM summary for a section."""
    utterances = [f"{c['participant']}: {c['content']}" for c in chunks]
    all_text = "\n".join(utterances)

    prompt = f"""Summarize this focus group discussion section in 2-3 sentences.
Focus on: key themes, voter sentiments, and notable quotes.

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
    return response.choices[0].message.content.strip()


def generate_all_parents(verbose: bool = True) -> List[Dict]:
    """Generate parent summaries for all focus groups."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    all_parents = []

    fg_ids = [d.name for d in CHUNKS_DIR.iterdir() if d.is_dir()]

    if verbose:
        print(f"Generating parents for {len(fg_ids)} focus groups...")

    for fg_idx, fg_id in enumerate(sorted(fg_ids)):
        fg_meta = load_focus_group_metadata(fg_id)
        sections = load_chunks_by_section(fg_id)

        if verbose:
            print(f"\n[{fg_idx+1}/{len(fg_ids)}] {fg_id} ({len(sections)} sections)")

        for section_name, chunks in sections.items():
            # Generate summary
            summary = generate_parent_summary(section_name, chunks, fg_meta, client)

            # Build parent content (for embedding)
            parent_content = f"""[{fg_meta['race_name']} | {fg_meta['location']}]
Section: {section_name}

{summary}"""

            parent = {
                "id": f"parent-{fg_id}-{section_name.lower().replace(' ', '-').replace(':', '-')[:50]}",
                "focus_group_id": fg_id,
                "section": section_name,
                "summary": summary,
                "content": parent_content,
                "chunk_count": len(chunks),
                "child_ids": [c["chunk_id"] for c in chunks],
            }
            all_parents.append(parent)

            if verbose:
                print(f"  - {section_name} ({len(chunks)} chunks)")

        # Rate limiting
        time.sleep(0.5)

    # Save parents
    with open(PARENTS_FILE, "w") as f:
        json.dump(all_parents, f, indent=2)

    if verbose:
        print(f"\nSaved {len(all_parents)} parents to {PARENTS_FILE}")

    return all_parents


def enrich_chunk(chunk: Dict, fg_meta: Dict) -> Dict:
    """Enrich a single chunk with context."""
    race_name = fg_meta.get("race_name", "Unknown Race")
    location = fg_meta.get("location", "Unknown Location")
    participant = chunk.get("participant", "Unknown")
    participant_profile = chunk.get("participant_profile", "")
    moderator_q = chunk.get("preceding_moderator_q", "")
    content = chunk.get("content", "")

    header = f"[{race_name} | {location} | {participant}: {participant_profile}]"
    enriched_parts = [header]
    if moderator_q:
        enriched_parts.append(f"Q: {moderator_q}")
    enriched_parts.append(f'"{content}"')

    enriched_content = "\n".join(enriched_parts)

    enriched_chunk = chunk.copy()
    enriched_chunk["content_original"] = content
    enriched_chunk["content"] = enriched_content

    return enriched_chunk


def enrich_all_children(verbose: bool = True) -> List[Dict]:
    """Enrich all chunks across all focus groups."""
    all_enriched = []

    fg_ids = [d.name for d in CHUNKS_DIR.iterdir() if d.is_dir()]

    if verbose:
        print(f"Enriching children for {len(fg_ids)} focus groups...")

    for fg_idx, fg_id in enumerate(sorted(fg_ids)):
        fg_meta = load_focus_group_metadata(fg_id)
        chunks_dir = CHUNKS_DIR / fg_id

        chunks = []
        for chunk_file in sorted(chunks_dir.glob("*.json")):
            if chunk_file.name == "all_chunks.json":
                continue
            with open(chunk_file) as f:
                chunks.append(json.load(f))

        # Enrich each chunk
        enriched_chunks = [enrich_chunk(c, fg_meta) for c in chunks]
        all_enriched.extend(enriched_chunks)

        # Save to enriched directory
        fg_output_dir = ENRICHED_DIR / fg_id
        fg_output_dir.mkdir(parents=True, exist_ok=True)

        for i, chunk in enumerate(enriched_chunks, 1):
            chunk_file = fg_output_dir / f"{i:03d}.json"
            with open(chunk_file, "w") as f:
                json.dump(chunk, f, indent=2)

        all_chunks_file = fg_output_dir / "all_chunks.json"
        with open(all_chunks_file, "w") as f:
            json.dump(enriched_chunks, f, indent=2)

        if verbose:
            print(f"  [{fg_idx+1}/{len(fg_ids)}] {fg_id}: {len(enriched_chunks)} chunks")

    if verbose:
        print(f"\nEnriched {len(all_enriched)} total chunks")
        print(f"Saved to {ENRICHED_DIR}")

    return all_enriched


def embed_hierarchical(verbose: bool = True):
    """Embed parents and children to Pinecone."""
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    bm25_encoder = BM25Encoder.default()
    bm25_encoder.load(str(DATA_DIR / "bm25_encoder.json"))

    # Load parents
    with open(PARENTS_FILE) as f:
        parents = json.load(f)

    if verbose:
        print(f"Embedding {len(parents)} parents...")

    # Embed parents
    parent_texts = [p["content"] for p in parents]
    parent_embeddings = []

    for i in range(0, len(parent_texts), 100):
        batch = parent_texts[i:i + 100]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        parent_embeddings.extend([item.embedding for item in response.data])
        if verbose:
            print(f"  Embedded parent batch {i//100 + 1}/{(len(parent_texts)+99)//100}")

    # Upsert parents
    parent_vectors = []
    for p, emb in zip(parents, parent_embeddings):
        sparse = bm25_encoder.encode_documents([p["content"]])[0]
        parent_vectors.append({
            "id": p["id"],
            "values": emb,
            "sparse_values": {"indices": sparse["indices"], "values": sparse["values"]},
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
        index.upsert(vectors=batch, namespace=NAMESPACE)

    if verbose:
        print(f"Upserted {len(parent_vectors)} parents")

    # Load and embed children
    all_children = []
    for fg_dir in sorted(ENRICHED_DIR.iterdir()):
        if not fg_dir.is_dir():
            continue
        all_chunks_file = fg_dir / "all_chunks.json"
        if all_chunks_file.exists():
            with open(all_chunks_file) as f:
                all_children.extend(json.load(f))

    if verbose:
        print(f"\nEmbedding {len(all_children)} children...")

    child_texts = [c["content"] for c in all_children]
    child_embeddings = []

    for i in range(0, len(child_texts), 100):
        batch = child_texts[i:i + 100]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        child_embeddings.extend([item.embedding for item in response.data])
        if verbose and (i % 500 == 0 or i + 100 >= len(child_texts)):
            print(f"  Embedded child batch {i//100 + 1}/{(len(child_texts)+99)//100}")
        time.sleep(0.3)  # Rate limiting

    # Upsert children
    child_vectors = []
    for c, emb in zip(all_children, child_embeddings):
        sparse = bm25_encoder.encode_documents([c["content"]])[0]
        child_vectors.append({
            "id": c["chunk_id"],
            "values": emb,
            "sparse_values": {"indices": sparse["indices"], "values": sparse["values"]},
            "metadata": {
                "type": "child",
                "focus_group_id": c["focus_group_id"],
                "participant": c["participant"],
                "participant_profile": c.get("participant_profile", ""),
                "section": c.get("section", ""),
                "content": c["content"][:1000],
                "content_original": c.get("content_original", "")[:500],
                "source_file": c.get("source_file", ""),
                "line_number": c.get("line_number", 0),
            }
        })

    for i in range(0, len(child_vectors), 100):
        batch = child_vectors[i:i + 100]
        index.upsert(vectors=batch, namespace=NAMESPACE)
        if verbose and (i % 500 == 0 or i + 100 >= len(child_vectors)):
            print(f"  Upserted child batch {i//100 + 1}/{(len(child_vectors)+99)//100}")

    if verbose:
        print(f"\nUpserted {len(child_vectors)} children")

    # Verify
    time.sleep(2)
    stats = index.describe_index_stats()
    ns_count = stats.namespaces.get(NAMESPACE, {}).get("vector_count", 0)
    print(f"\nTotal vectors in '{NAMESPACE}': {ns_count}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build hierarchical index")
    parser.add_argument("--generate-parents", action="store_true", help="Generate parent summaries")
    parser.add_argument("--enrich-children", action="store_true", help="Enrich all children")
    parser.add_argument("--embed", action="store_true", help="Embed to Pinecone")
    parser.add_argument("--all", action="store_true", help="Do everything")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()
    verbose = not args.quiet

    if args.all or args.generate_parents:
        print("=" * 60)
        print("STEP 1: Generating parent summaries")
        print("=" * 60)
        generate_all_parents(verbose)

    if args.all or args.enrich_children:
        print("\n" + "=" * 60)
        print("STEP 2: Enriching children")
        print("=" * 60)
        enrich_all_children(verbose)

    if args.all or args.embed:
        print("\n" + "=" * 60)
        print("STEP 3: Embedding to Pinecone")
        print("=" * 60)
        embed_hierarchical(verbose)

    if not any([args.all, args.generate_parents, args.enrich_children, args.embed]):
        parser.print_help()


if __name__ == "__main__":
    main()
