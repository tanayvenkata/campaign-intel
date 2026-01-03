#!/usr/bin/env python3
"""
ColBERT indexing for focus group chunks.
Uses ColBERT for token-level late interaction retrieval.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import DATA_DIR


def load_all_chunks() -> List[Dict]:
    """Load all chunks from enriched directory."""
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


def create_colbert_index(
    index_name: str = "focus-group-colbert",
    max_chunks: int = None,
    checkpoint: str = "colbert-ir/colbertv2.0"
):
    """Create ColBERT index from chunks."""
    from colbert import Indexer
    from colbert.infra import Run, RunConfig, ColBERTConfig

    # Load chunks
    print("Loading chunks...")
    chunks = load_all_chunks()

    if max_chunks:
        chunks = chunks[:max_chunks]

    print(f"Indexing {len(chunks)} chunks with ColBERT...")

    # Prepare documents and IDs
    documents = [chunk.get("content", chunk.get("content_original", "")) for chunk in chunks]
    doc_ids = [chunk["chunk_id"] for chunk in chunks]

    # Save documents to temp file (ColBERT needs file input)
    index_dir = DATA_DIR / "colbert_index"
    index_dir.mkdir(parents=True, exist_ok=True)

    collection_path = index_dir / "collection.tsv"
    with open(collection_path, "w") as f:
        for i, (doc_id, doc) in enumerate(zip(doc_ids, documents)):
            # TSV format: id \t text
            doc_clean = doc.replace("\t", " ").replace("\n", " ")
            f.write(f"{i}\t{doc_clean}\n")

    # Save mapping of index position to chunk_id
    mapping_path = index_dir / "id_mapping.json"
    with open(mapping_path, "w") as f:
        json.dump({str(i): doc_id for i, doc_id in enumerate(doc_ids)}, f, indent=2)

    print(f"Collection saved to {collection_path}")
    print(f"ID mapping saved to {mapping_path}")

    # Create ColBERT config
    config = ColBERTConfig(
        nbits=2,
        doc_maxlen=256,
        checkpoint=checkpoint
    )

    # Index
    start_time = time.time()

    with Run().context(RunConfig(nranks=1, experiment="focus-group")):
        indexer = Indexer(checkpoint=checkpoint, config=config)
        indexer.index(
            name=index_name,
            collection=str(collection_path),
            overwrite=True
        )

    elapsed = time.time() - start_time
    print(f"\nIndexing complete in {elapsed:.1f} seconds")
    print(f"Index location: experiments/focus-group/indexes/{index_name}")

    return index_dir


def main():
    """Create ColBERT index."""
    import argparse

    parser = argparse.ArgumentParser(description="Create ColBERT index")
    parser.add_argument("--index-name", default="focus-group-colbert",
                        help="Name for the ColBERT index")
    parser.add_argument("--max-chunks", type=int, help="Limit chunks (for testing)")
    parser.add_argument("--checkpoint", default="colbert-ir/colbertv2.0",
                        help="ColBERT checkpoint to use")

    args = parser.parse_args()

    create_colbert_index(
        index_name=args.index_name,
        max_chunks=args.max_chunks,
        checkpoint=args.checkpoint
    )


if __name__ == "__main__":
    main()
