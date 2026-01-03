#!/usr/bin/env python3
"""
Embed enriched chunks to Pinecone namespace for testing.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import (
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    DATA_DIR,
)

import openai
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder


def load_enriched_chunks(fg_id: str) -> List[Dict]:
    """Load enriched chunks for a focus group."""
    enriched_dir = DATA_DIR / "chunks_enriched" / fg_id
    all_chunks_file = enriched_dir / "all_chunks.json"

    if not all_chunks_file.exists():
        raise FileNotFoundError(f"Enriched chunks not found: {all_chunks_file}")

    with open(all_chunks_file) as f:
        return json.load(f)


def create_embeddings(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Create dense embeddings using OpenAI API."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"  Embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch
        )

        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


def embed_to_namespace(
    chunks: List[Dict],
    namespace: str,
    batch_size: int = 100
):
    """Embed chunks and upsert to specified namespace."""

    # Initialize Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)

    # Load BM25 encoder
    bm25_path = DATA_DIR / "bm25_encoder.json"
    bm25_encoder = BM25Encoder.default()
    bm25_encoder.load(str(bm25_path))

    # Get texts (enriched content)
    texts = [chunk["content"] for chunk in chunks]

    print(f"\nCreating embeddings for {len(texts)} chunks...")
    dense_embeddings = create_embeddings(texts)

    print(f"\nCreating sparse vectors...")
    sparse_vectors = []
    for text in texts:
        sparse = bm25_encoder.encode_documents([text])[0]
        sparse_vectors.append({
            "indices": sparse["indices"],
            "values": sparse["values"]
        })

    print(f"\nUpserting to namespace: {namespace}")

    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_dense = dense_embeddings[i:i + batch_size]
        batch_sparse = sparse_vectors[i:i + batch_size]

        vectors = []
        for chunk, dense, sparse in zip(batch_chunks, batch_dense, batch_sparse):
            vectors.append({
                "id": chunk["chunk_id"],
                "values": dense,
                "sparse_values": sparse,
                "metadata": {
                    "focus_group_id": chunk["focus_group_id"],
                    "participant": chunk["participant"],
                    "participant_profile": chunk.get("participant_profile", ""),
                    "section": chunk.get("section", ""),
                    "content": chunk["content"][:1000],  # Enriched content
                    "content_original": chunk.get("content_original", "")[:500],
                    "source_file": chunk.get("source_file", ""),
                    "line_number": chunk.get("line_number", 0),
                }
            })

        print(f"  Upserting batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}")
        index.upsert(vectors=vectors, namespace=namespace)

    # Verify
    time.sleep(2)  # Wait for indexing
    stats = index.describe_index_stats()
    print(f"\nIndex stats: {stats}")

    ns_count = stats.namespaces.get(namespace, {}).get("vector_count", 0)
    print(f"Vectors in '{namespace}' namespace: {ns_count}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Embed enriched chunks to Pinecone namespace")
    parser.add_argument("focus_group", help="Focus group ID to embed")
    parser.add_argument("--namespace", type=str, default="enriched-test",
                        help="Pinecone namespace (default: enriched-test)")

    args = parser.parse_args()

    print(f"Loading enriched chunks for: {args.focus_group}")
    chunks = load_enriched_chunks(args.focus_group)
    print(f"Loaded {len(chunks)} chunks")

    embed_to_namespace(chunks, args.namespace)

    print("\nDone!")


if __name__ == "__main__":
    main()
