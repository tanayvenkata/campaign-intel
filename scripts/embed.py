#!/usr/bin/env python3
"""
Embed all chunks with bge-m3 and upload to Pinecone.
Uses hierarchical structure: parents (section summaries) + children (utterances).

Supports:
- Focus group chunks (type: parent, child)
- Strategy memo chunks (type: strategy_parent, strategy_memo)

Run: python scripts/embed.py
      python scripts/embed.py --strategy-only  # Just embed strategy memos
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import PINECONE_API_KEY, DATA_DIR, FOCUS_GROUPS_DIR, EMBEDDING_MODEL_LOCAL
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

# Constants - bge-m3 uses 1024 dimensions
INDEX_NAME = "focus-group-v3"
MODEL_NAME = EMBEDDING_MODEL_LOCAL

# Auto-detect dimension based on model
MODEL_DIMENSIONS = {
    "BAAI/bge-m3": 1024,
    "intfloat/e5-base-v2": 768,
    "BAAI/bge-base-en-v1.5": 768,
}
DIMENSION = MODEL_DIMENSIONS.get(MODEL_NAME, 1024)


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
    """Load hierarchical parents for focus groups."""
    parents_file = DATA_DIR / "hierarchical_parents.json"
    if not parents_file.exists():
        print(f"Warning: Parents file not found: {parents_file}")
        return []

    with open(parents_file) as f:
        return json.load(f)


def load_strategy_chunks() -> List[Dict]:
    """Load all strategy memo chunks (children)."""
    strategy_dir = DATA_DIR / "strategy_chunks"
    all_chunks = []

    for race_dir in sorted(strategy_dir.iterdir()):
        if race_dir.is_dir() and race_dir.name.startswith("race-"):
            chunks_file = race_dir / "all_chunks.json"
            if chunks_file.exists():
                with open(chunks_file) as f:
                    chunks = json.load(f)
                    all_chunks.extend(chunks)

    return all_chunks


def load_strategy_parents() -> List[Dict]:
    """Load hierarchical parents for strategy memos."""
    parents_file = DATA_DIR / "strategy_chunks" / "hierarchical_parents.json"
    if not parents_file.exists():
        print(f"Warning: Strategy parents file not found: {parents_file}")
        return []

    with open(parents_file) as f:
        return json.load(f)


def embed_texts(
    model: SentenceTransformer,
    texts: List[str],
    batch_size: int = 64
) -> List[List[float]]:
    """Embed texts with sentence-transformer model.

    Note: bge-m3 doesn't require prefix, E5 models do.
    For simplicity, we skip prefix since bge-m3 is now default.
    """
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=batch_size)
    return embeddings.tolist()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Embed with bge-m3 to Pinecone")
    parser.add_argument("--skip-parents", action="store_true", help="Skip FG parent embeddings")
    parser.add_argument("--skip-children", action="store_true", help="Skip FG children embeddings")
    parser.add_argument("--skip-strategy", action="store_true", help="Skip strategy memo embeddings")
    parser.add_argument("--strategy-only", action="store_true", help="Only embed strategy memos (additive)")
    parser.add_argument("--dry-run", action="store_true", help="Don't upload to Pinecone")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear existing vectors (additive mode)")

    args = parser.parse_args()

    # Strategy-only implies no-clear and skip FG content
    if args.strategy_only:
        args.skip_parents = True
        args.skip_children = True
        args.no_clear = True

    print("=" * 60)
    print("EMBEDDING PIPELINE")
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

    # Clear existing vectors (unless --no-clear or --strategy-only)
    if not args.no_clear:
        print("\nClearing existing vectors...")
        try:
            index.delete(delete_all=True)
            time.sleep(5)
        except Exception as e:
            print(f"  Note: {e}")
    else:
        print("\nAdditive mode: keeping existing vectors")

    all_vectors = []

    # ========================================
    # FOCUS GROUP CONTENT
    # ========================================

    # Process FG parents
    if not args.skip_parents:
        print("\n" + "=" * 60)
        print("STEP 1: Embedding FG Parents")
        print("=" * 60)

        parents = load_all_parents()
        print(f"Loaded {len(parents)} FG parents")

        if parents:
            parent_texts = [p["content"] for p in parents]
            print("Embedding FG parents...")
            parent_embeddings = embed_texts(model, parent_texts)

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

            print(f"Prepared {len(parents)} FG parent vectors")

    # Process FG children
    if not args.skip_children:
        print("\n" + "=" * 60)
        print("STEP 2: Embedding FG Children")
        print("=" * 60)

        children = load_all_children()
        print(f"Loaded {len(children)} FG children")

        # Use enriched content for embedding
        child_texts = [c.get("content", c.get("content_original", "")) for c in children]
        print("Embedding FG children...")
        child_embeddings = embed_texts(model, child_texts)

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

        print(f"Prepared {len(children)} FG child vectors")

    # ========================================
    # STRATEGY MEMO CONTENT
    # ========================================

    if not args.skip_strategy:
        # Process strategy parents
        print("\n" + "=" * 60)
        print("STEP 3: Embedding Strategy Parents")
        print("=" * 60)

        strategy_parents = load_strategy_parents()
        print(f"Loaded {len(strategy_parents)} strategy parents")

        if strategy_parents:
            parent_texts = [p["content"] for p in strategy_parents]
            print("Embedding strategy parents...")
            parent_embeddings = embed_texts(model, parent_texts)

            for parent, embedding in zip(strategy_parents, parent_embeddings):
                all_vectors.append({
                    "id": parent["id"],
                    "values": embedding,
                    "metadata": {
                        "type": "strategy_parent",
                        "race_id": parent["race_id"],
                        "section": parent["section"],
                        "summary": parent.get("summary", "")[:500],
                        "content": parent["content"][:1000],
                        "outcome": parent.get("outcome", ""),
                        "state": parent.get("state", ""),
                        "year": parent.get("year", 0),
                        "margin": parent.get("margin", 0.0),
                        "child_ids": json.dumps(parent.get("child_ids", []))
                    }
                })

            print(f"Prepared {len(strategy_parents)} strategy parent vectors")

        # Process strategy children (chunks)
        print("\n" + "=" * 60)
        print("STEP 4: Embedding Strategy Children")
        print("=" * 60)

        strategy_chunks = load_strategy_chunks()
        print(f"Loaded {len(strategy_chunks)} strategy chunks")

        if strategy_chunks:
            chunk_texts = [c["content"] for c in strategy_chunks]
            print("Embedding strategy chunks...")
            chunk_embeddings = embed_texts(model, chunk_texts)

            for chunk, embedding in zip(strategy_chunks, chunk_embeddings):
                all_vectors.append({
                    "id": chunk["chunk_id"],
                    "values": embedding,
                    "metadata": {
                        "type": "strategy_memo",
                        "race_id": chunk["race_id"],
                        "section": chunk.get("section") or "",
                        "subsection": chunk.get("subsection") or "",  # Handle null
                        "content": chunk["content"][:1000],
                        "outcome": chunk.get("outcome") or "",
                        "state": chunk.get("state") or "",
                        "year": chunk.get("year") or 0,
                        "margin": chunk.get("margin") or 0.0,
                        "source_file": chunk.get("source_file") or "",
                        "line_number": chunk.get("line_number") or 0,
                    }
                })

            print(f"Prepared {len(strategy_chunks)} strategy chunk vectors")

    # ========================================
    # UPLOAD TO PINECONE
    # ========================================

    if not args.dry_run:
        print("\n" + "=" * 60)
        print("UPLOADING TO PINECONE")
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
        print(f"\n[DRY RUN] Would upload {len(all_vectors)} vectors")

    print("\nDone!")


if __name__ == "__main__":
    main()
