#!/usr/bin/env python3
"""
Embed all focus group chunks and upsert to Pinecone.
Uses OpenAI for dense embeddings and BM25 for sparse vectors.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict
import time

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import (
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_CLOUD,
    PINECONE_REGION,
    CHUNKS_DIR,
    DATA_DIR,
)

# Lazy imports for optional dependencies
openai = None
pinecone = None
BM25Encoder = None


def load_dependencies():
    """Load optional dependencies with helpful error messages."""
    global openai, pinecone, BM25Encoder

    try:
        import openai as _openai
        openai = _openai
    except ImportError:
        raise ImportError("openai not installed. Run: pip install openai")

    try:
        from pinecone import Pinecone, ServerlessSpec
        pinecone = (Pinecone, ServerlessSpec)
    except ImportError:
        raise ImportError("pinecone not installed. Run: pip install pinecone-client")

    try:
        from pinecone_text.sparse import BM25Encoder as _BM25Encoder
        BM25Encoder = _BM25Encoder
    except ImportError:
        raise ImportError("pinecone-text not installed. Run: pip install pinecone-text")


def load_all_chunks() -> List[Dict]:
    """Load all chunks from all focus groups."""
    chunks = []

    for fg_dir in sorted(CHUNKS_DIR.iterdir()):
        if not fg_dir.is_dir():
            continue

        all_chunks_file = fg_dir / "all_chunks.json"
        if all_chunks_file.exists():
            with open(all_chunks_file) as f:
                fg_chunks = json.load(f)
                chunks.extend(fg_chunks)

    return chunks


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

        # Rate limiting
        if i + batch_size < len(texts):
            time.sleep(0.5)

    return all_embeddings


def fit_bm25_encoder(chunks: List[Dict]) -> "BM25Encoder":
    """Fit BM25 encoder on corpus."""
    corpus = [chunk["content"] for chunk in chunks]

    # Use default BM25 encoder and fit on corpus
    encoder = BM25Encoder.default()
    encoder.fit(corpus)

    return encoder


def create_sparse_vectors(encoder, texts: List[str]) -> List[Dict]:
    """Create sparse vectors using fitted BM25 encoder."""
    sparse_vectors = []

    for text in texts:
        sparse = encoder.encode_documents([text])[0]
        sparse_vectors.append({
            "indices": sparse["indices"],
            "values": sparse["values"]
        })

    return sparse_vectors


def create_pinecone_index():
    """Create Pinecone index if it doesn't exist."""
    Pinecone, ServerlessSpec = pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Check if index exists
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if PINECONE_INDEX_NAME not in existing_indexes:
        print(f"Creating index '{PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=1536,  # text-embedding-3-small dimension
            metric="dotproduct",  # Required for hybrid search
            spec=ServerlessSpec(
                cloud=PINECONE_CLOUD,
                region=PINECONE_REGION
            )
        )
        # Wait for index to be ready
        print("Waiting for index to be ready...")
        time.sleep(10)
    else:
        print(f"Index '{PINECONE_INDEX_NAME}' already exists")

    return pc.Index(PINECONE_INDEX_NAME)


def upsert_to_pinecone(
    index,
    chunks: List[Dict],
    dense_embeddings: List[List[float]],
    sparse_vectors: List[Dict],
    batch_size: int = 100
):
    """Upsert vectors to Pinecone with metadata."""

    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_dense = dense_embeddings[i:i + batch_size]
        batch_sparse = sparse_vectors[i:i + batch_size]

        vectors = []
        for j, (chunk, dense, sparse) in enumerate(zip(batch_chunks, batch_dense, batch_sparse)):
            vectors.append({
                "id": chunk["chunk_id"],
                "values": dense,
                "sparse_values": sparse,
                "metadata": {
                    "focus_group_id": chunk["focus_group_id"],
                    "participant": chunk["participant"],
                    "participant_profile": chunk.get("participant_profile", ""),
                    "section": chunk.get("section", ""),
                    "content": chunk["content"][:1000],  # Pinecone metadata limit
                    "source_file": chunk.get("source_file", ""),
                    "line_number": chunk.get("line_number", 0),
                }
            })

        print(f"  Upserting batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}")
        index.upsert(vectors=vectors)

        # Rate limiting
        if i + batch_size < len(chunks):
            time.sleep(0.5)


def save_bm25_encoder(encoder, path: Path):
    """Save fitted BM25 encoder for use during retrieval."""
    encoder.dump(str(path))
    print(f"Saved BM25 encoder to {path}")


def main():
    print("=" * 60)
    print("Focus Group Embedding Pipeline")
    print("=" * 60)

    # Load dependencies
    print("\nLoading dependencies...")
    load_dependencies()

    # Validate config
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in .env")
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY not found in .env")

    # Load chunks
    print("\nLoading chunks...")
    chunks = load_all_chunks()
    print(f"Loaded {len(chunks)} chunks")

    # Create dense embeddings
    print("\nCreating dense embeddings...")
    texts = [chunk["content"] for chunk in chunks]
    dense_embeddings = create_embeddings(texts)
    print(f"Created {len(dense_embeddings)} dense embeddings")

    # Fit and create sparse vectors
    print("\nFitting BM25 encoder...")
    bm25_encoder = fit_bm25_encoder(chunks)

    print("\nCreating sparse vectors...")
    sparse_vectors = create_sparse_vectors(bm25_encoder, texts)
    print(f"Created {len(sparse_vectors)} sparse vectors")

    # Save BM25 encoder for retrieval
    bm25_path = DATA_DIR / "bm25_encoder.json"
    save_bm25_encoder(bm25_encoder, bm25_path)

    # Create/get Pinecone index
    print("\nSetting up Pinecone index...")
    index = create_pinecone_index()

    # Upsert to Pinecone
    print("\nUpserting to Pinecone...")
    upsert_to_pinecone(index, chunks, dense_embeddings, sparse_vectors)

    # Verify
    stats = index.describe_index_stats()
    print(f"\nIndex stats: {stats}")

    print("\n" + "=" * 60)
    print("Embedding complete!")
    print(f"  - Chunks embedded: {len(chunks)}")
    print(f"  - Index: {PINECONE_INDEX_NAME}")
    print(f"  - BM25 encoder saved: {bm25_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
