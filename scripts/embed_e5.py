#!/usr/bin/env python3
"""
Embed all chunks with E5-base and upload to Pinecone.
Uses hierarchical structure: parents (section summaries) + children (utterances).
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import PINECONE_API_KEY, DATA_DIR, FOCUS_GROUPS_DIR
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

# Constants
INDEX_NAME = "focus-group-v2"
DIMENSION = 768  # E5-base dimension
MODEL_NAME = "intfloat/e5-base-v2"


def load_all_children() -> List[Dict]:
    """Load all enriched children from all focus groups."""
    chunks_dir = DATA_DIR / "chunks_enriched"
    all_chunks = []

    for fg_dir in sorted(chunks_dir.iterdir()):
        if fg_dir.is_dir():
            chunks_file = fg_dir / "all_chunks.json"
            if chunks_file.exists():
                with open(chunks_file) as f:
                    chunks = json.load(f)
                    all_chunks.extend(chunks)

    return all_chunks


def load_all_parents() -> List[Dict]:
    """Load hierarchical parents."""
    parents_file = DATA_DIR / "hierarchical_parents.json"
    if not parents_file.exists():
        print(f"Warning: Parents file not found: {parents_file}")
        return []

    with open(parents_file) as f:
        return json.load(f)


def embed_with_e5(
    model: SentenceTransformer,
    texts: List[str],
    prefix: str = "passage: ",
    batch_size: int = 64
) -> List[List[float]]:
    """Embed texts with E5 model (requires prefix)."""
    prefixed = [f"{prefix}{t}" for t in texts]
    embeddings = model.encode(prefixed, show_progress_bar=True, batch_size=batch_size)
    return embeddings.tolist()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Embed with E5-base to Pinecone")
    parser.add_argument("--skip-parents", action="store_true", help="Skip parent embeddings")
    parser.add_argument("--skip-children", action="store_true", help="Skip children embeddings")
    parser.add_argument("--dry-run", action="store_true", help="Don't upload to Pinecone")

    args = parser.parse_args()

    print("=" * 60)
    print("E5-BASE EMBEDDING PIPELINE")
    print("=" * 60)

    # Load model
    print(f"\nLoading {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    # Initialize Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Check if index exists, create if not
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"\nCreating index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric="cosine",
            spec={"serverless": {"cloud": "aws", "region": "us-east-1"}}
        )
        time.sleep(10)  # Wait for index to be ready

    index = pc.Index(INDEX_NAME)

    # Clear existing vectors
    print("\nClearing existing vectors...")
    try:
        index.delete(delete_all=True)
        time.sleep(5)
    except Exception as e:
        print(f"  Note: {e}")

    all_vectors = []

    # Process parents
    if not args.skip_parents:
        print("\n" + "=" * 60)
        print("STEP 1: Embedding Parents")
        print("=" * 60)

        parents = load_all_parents()
        print(f"Loaded {len(parents)} parents")

        if parents:
            parent_texts = [p["content"] for p in parents]
            print("Embedding parents...")
            parent_embeddings = embed_with_e5(model, parent_texts)

            for parent, embedding in zip(parents, parent_embeddings):
                all_vectors.append({
                    "id": parent["id"],
                    "values": embedding,
                    "metadata": {
                        "type": "parent",
                        "focus_group_id": parent["focus_group_id"],
                        "section": parent["section"],
                        "content": parent["content"][:1000],
                        "child_ids": json.dumps(parent.get("child_ids", []))
                    }
                })

            print(f"Prepared {len(parents)} parent vectors")

    # Process children
    if not args.skip_children:
        print("\n" + "=" * 60)
        print("STEP 2: Embedding Children")
        print("=" * 60)

        children = load_all_children()
        print(f"Loaded {len(children)} children")

        # Use enriched content for embedding
        child_texts = [c.get("content", c.get("content_original", "")) for c in children]
        print("Embedding children...")
        child_embeddings = embed_with_e5(model, child_texts)

        for child, embedding in zip(children, child_embeddings):
            all_vectors.append({
                "id": child["chunk_id"],
                "values": embedding,
                "metadata": {
                    "type": "child",
                    "focus_group_id": child["focus_group_id"],
                    "participant": child.get("participant", ""),
                    "participant_profile": child.get("participant_profile", ""),
                    "section": child.get("section", ""),
                    "content": child.get("content", "")[:1000],
                    "content_original": child.get("content_original", "")[:500],
                    "source_file": child.get("source_file", ""),
                    "line_number": child.get("line_number", 0),
                    "preceding_moderator_q": child.get("preceding_moderator_q", ""),
                }
            })

        print(f"Prepared {len(children)} child vectors")

    # Upload to Pinecone
    if not args.dry_run:
        print("\n" + "=" * 60)
        print("STEP 3: Uploading to Pinecone")
        print("=" * 60)

        batch_size = 100
        for i in range(0, len(all_vectors), batch_size):
            batch = all_vectors[i:i + batch_size]
            index.upsert(vectors=batch)

            if (i + batch_size) % 500 == 0 or i + batch_size >= len(all_vectors):
                print(f"  Uploaded {min(i + batch_size, len(all_vectors))}/{len(all_vectors)}")

        # Verify
        time.sleep(3)
        stats = index.describe_index_stats()
        print(f"\nIndex stats: {stats.total_vector_count} vectors")
    else:
        print("\n[DRY RUN] Would upload {len(all_vectors)} vectors")

    print("\nDone!")


if __name__ == "__main__":
    main()
