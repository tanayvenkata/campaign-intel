#!/usr/bin/env python3
"""
Embed Doc2Query expanded chunks to Pinecone.
Uses the expanded content (with generated search queries) for embeddings.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import DATA_DIR, PINECONE_API_KEY


def load_doc2query_chunks() -> List[Dict]:
    """Load Doc2Query expanded chunks."""
    chunks_file = DATA_DIR / "chunks_doc2query" / "all_chunks_doc2query.json"
    with open(chunks_file) as f:
        return json.load(f)


def embed_and_upsert(
    namespace: str = "doc2query",
    batch_size: int = 96,
    max_chunks: int = None,
    verbose: bool = True
):
    """Embed Doc2Query chunks and upsert to Pinecone."""
    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer

    # Load model
    print("Loading E5-base model...")
    model = SentenceTransformer("intfloat/e5-base-v2")

    # Load chunks
    print("Loading Doc2Query chunks...")
    chunks = load_doc2query_chunks()

    if max_chunks:
        chunks = chunks[:max_chunks]

    print(f"Embedding {len(chunks)} chunks...")

    # Connect to Pinecone (V2 index with 768 dims)
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index("focus-group-v2")

    # Embed and upsert in batches
    start_time = time.time()
    total_upserted = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        # Use the doc2query expanded content
        texts = [f"passage: {c.get('content_doc2query', c.get('content', ''))}" for c in batch]

        # Embed
        embeddings = model.encode(texts, normalize_embeddings=True)

        # Prepare vectors
        vectors = []
        for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
            vectors.append({
                "id": chunk["chunk_id"],
                "values": embedding.tolist(),
                "metadata": {
                    "chunk_id": chunk["chunk_id"],
                    "focus_group_id": chunk.get("focus_group_id", ""),
                    "content": chunk.get("content_original", chunk.get("content", ""))[:1000],
                    "content_doc2query": chunk.get("content_doc2query", "")[:1500],
                    "type": "doc2query"
                }
            })

        # Upsert
        index.upsert(vectors=vectors, namespace=namespace)
        total_upserted += len(vectors)

        if verbose and (i + batch_size) % 500 < batch_size:
            elapsed = time.time() - start_time
            rate = total_upserted / elapsed
            print(f"  [{total_upserted}/{len(chunks)}] {rate:.1f} vectors/sec")

    elapsed = time.time() - start_time
    print(f"\nUpserted {total_upserted} vectors to namespace '{namespace}'")
    print(f"Total time: {elapsed:.1f} seconds")

    return total_upserted


def main():
    """Embed Doc2Query chunks."""
    import argparse

    parser = argparse.ArgumentParser(description="Embed Doc2Query chunks to Pinecone")
    parser.add_argument("--namespace", default="doc2query",
                        help="Pinecone namespace for Doc2Query vectors")
    parser.add_argument("--max-chunks", type=int, help="Limit chunks (for testing)")
    parser.add_argument("--batch-size", type=int, default=96)

    args = parser.parse_args()

    embed_and_upsert(
        namespace=args.namespace,
        batch_size=args.batch_size,
        max_chunks=args.max_chunks,
        verbose=True
    )


if __name__ == "__main__":
    main()
