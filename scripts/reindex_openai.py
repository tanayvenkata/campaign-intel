#!/usr/bin/env python3
"""
Re-index Pinecone with OpenAI embeddings.

Creates vectors in a new 'openai' namespace, keeping BGE-M3 vectors as backup.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
from scripts.embeddings import OpenAIEmbedder

# Config
INDEX_NAME = "focus-group-v3"
NAMESPACE = "openai"  # New namespace for OpenAI embeddings
DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 100


def load_all_chunks():
    """Load all chunks from enriched data (focus groups + strategy memos)."""
    chunks = []

    # Focus group chunks
    print("  Loading focus group chunks...")
    chunks_dir = DATA_DIR / "chunks_enriched"
    for fg_dir in sorted(chunks_dir.iterdir()):
        if fg_dir.is_dir():
            chunk_file = fg_dir / "all_chunks.json"
            if chunk_file.exists():
                with open(chunk_file) as f:
                    fg_chunks = json.load(f)
                    chunks.extend(fg_chunks)
                    print(f"    Loaded {len(fg_chunks)} chunks from {fg_dir.name}")

    # Strategy memo chunks
    print("  Loading strategy memo chunks...")
    strategy_dir = DATA_DIR / "strategy_chunks"
    for race_dir in sorted(strategy_dir.iterdir()):
        if race_dir.is_dir() and race_dir.name.startswith("race-"):
            chunk_file = race_dir / "all_chunks.json"
            if chunk_file.exists():
                with open(chunk_file) as f:
                    strat_chunks = json.load(f)
                    # Mark as strategy_memo type for filtering
                    for chunk in strat_chunks:
                        chunk["type"] = "strategy_memo"
                    chunks.extend(strat_chunks)
                    print(f"    Loaded {len(strat_chunks)} chunks from {race_dir.name}")

    return chunks


def load_hierarchical_parents():
    """Load parent chunks for hierarchical retrieval (focus groups + strategy memos)."""
    parents = []

    # Focus group parents
    fg_parents_file = DATA_DIR / "hierarchical_parents.json"
    if fg_parents_file.exists():
        with open(fg_parents_file) as f:
            fg_parents = json.load(f)
            parents.extend(fg_parents)
            print(f"  Loaded {len(fg_parents)} focus group parents")

    # Strategy memo parents
    strat_parents_file = DATA_DIR / "strategy_chunks" / "hierarchical_parents.json"
    if strat_parents_file.exists():
        with open(strat_parents_file) as f:
            strat_parents = json.load(f)
            # Mark as strategy type for filtering
            for parent in strat_parents:
                parent["type"] = "strategy_parent"
            parents.extend(strat_parents)
            print(f"  Loaded {len(strat_parents)} strategy memo parents")

    return parents


def main():
    print("=" * 60)
    print("Re-indexing Pinecone with OpenAI embeddings")
    print("=" * 60)

    # Initialize
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(INDEX_NAME)
    embedder = OpenAIEmbedder(dimensions=1024)

    # Load data
    print("\nLoading chunks...")
    chunks = load_all_chunks()
    print(f"Total chunks: {len(chunks)}")

    parents = load_hierarchical_parents()
    print(f"Hierarchical parents: {len(parents)}")

    # Embed and upsert chunks
    print(f"\nEmbedding and upserting to namespace '{NAMESPACE}'...")

    # Prepare texts for embedding
    texts = []
    for chunk in chunks:
        # Same text as BGE-M3 indexing: content + profile
        text = chunk.get("content", "")
        profile = chunk.get("participant_profile", "")
        if profile:
            text = f"{text}\n\nParticipant: {profile}"
        texts.append(text)

    # Embed in batches
    print(f"Embedding {len(texts)} texts...")
    embeddings = embedder.encode(texts, show_progress_bar=True)

    # Prepare vectors for upsert
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = chunk.get("chunk_id", f"chunk-{i}")
        chunk_type = chunk.get("type", "child")

        if chunk_type == "strategy_memo":
            # Strategy memo metadata
            metadata = {
                "race_id": chunk.get("race_id", ""),
                "section": chunk.get("section", ""),
                "subsection": chunk.get("subsection", "") or "",
                "content": chunk.get("content", "")[:1000],
                "content_original": chunk.get("content", ""),
                "state": chunk.get("state", ""),
                "year": chunk.get("year", 0),
                "outcome": chunk.get("outcome", ""),
                "margin": chunk.get("margin", 0.0),
                "source_file": chunk.get("source_file", ""),
                "line_number": chunk.get("line_number", 0),
                "type": "strategy_memo",
            }
        else:
            # Focus group metadata (default)
            metadata = {
                "focus_group_id": chunk.get("focus_group_id", ""),
                "participant": chunk.get("participant", ""),
                "participant_profile": chunk.get("participant_profile", ""),
                "section": chunk.get("section", ""),
                "content": chunk.get("content", "")[:1000],
                "content_original": chunk.get("content", ""),
                "source_file": chunk.get("source_file", ""),
                "line_number": chunk.get("line_number", 0),
                "preceding_moderator_q": chunk.get("preceding_moderator_q", ""),
                "type": "child",
            }

        vectors.append({
            "id": chunk_id,
            "values": embedding,
            "metadata": metadata,
        })

    # Upsert in batches
    print(f"\nUpserting {len(vectors)} vectors...")
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        index.upsert(vectors=batch, namespace=NAMESPACE)
        print(f"  Upserted {min(i + BATCH_SIZE, len(vectors))}/{len(vectors)}")

    # Now embed and upsert parent chunks
    print(f"\nProcessing {len(parents)} parent chunks...")
    parent_vectors = []

    # Parents is a list of dicts with 'id' field
    parent_texts = [p.get("summary", p.get("content", "")) for p in parents]
    parent_embeddings = embedder.encode(parent_texts, show_progress_bar=True)

    for parent, embedding in zip(parents, parent_embeddings):
        parent_id = parent.get("id", "")
        parent_type = parent.get("type", "parent")

        if parent_type == "strategy_parent":
            # Strategy memo parent metadata
            metadata = {
                "race_id": parent.get("race_id", ""),
                "section": parent.get("section", ""),
                "content": parent.get("summary", parent.get("content", ""))[:1000],
                "content_original": parent.get("summary", parent.get("content", "")),
                "child_ids": json.dumps(parent.get("child_chunk_ids", [])),
                "type": "strategy_parent",
            }
        else:
            # Focus group parent metadata (default)
            metadata = {
                "focus_group_id": parent.get("focus_group_id", ""),
                "section": parent.get("section", ""),
                "content": parent.get("summary", parent.get("content", ""))[:1000],
                "content_original": parent.get("summary", parent.get("content", "")),
                "child_ids": json.dumps(parent.get("child_chunk_ids", [])),
                "type": "parent",
            }

        parent_vectors.append({
            "id": parent_id,
            "values": embedding,
            "metadata": metadata,
        })

    # Upsert parents
    for i in range(0, len(parent_vectors), BATCH_SIZE):
        batch = parent_vectors[i:i + BATCH_SIZE]
        index.upsert(vectors=batch, namespace=NAMESPACE)
        print(f"  Upserted parents {min(i + BATCH_SIZE, len(parent_vectors))}/{len(parent_vectors)}")

    # Verify
    print("\nVerifying...")
    stats = index.describe_index_stats()
    openai_count = stats.namespaces.get(NAMESPACE, {}).vector_count if NAMESPACE in stats.namespaces else 0
    print(f"Vectors in '{NAMESPACE}' namespace: {openai_count}")

    print("\n" + "=" * 60)
    print("Done! OpenAI embeddings indexed to 'openai' namespace.")
    print("Update retrieval code to use namespace='openai'")
    print("=" * 60)


if __name__ == "__main__":
    main()
