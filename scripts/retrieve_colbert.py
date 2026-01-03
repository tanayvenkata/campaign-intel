#!/usr/bin/env python3
"""
ColBERT retrieval for focus group chunks.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import DATA_DIR


@dataclass
class ColBERTResult:
    """Result from ColBERT search."""
    chunk_id: str
    content: str
    score: float
    focus_group_id: str
    metadata: Dict


class ColBERTRetriever:
    """ColBERT-based retriever for focus group content."""

    def __init__(
        self,
        index_name: str = "focus-group-colbert",
        checkpoint: str = "colbert-ir/colbertv2.0",
        verbose: bool = False
    ):
        from colbert import Searcher
        from colbert.infra import Run, RunConfig, ColBERTConfig

        self.verbose = verbose
        self.index_name = index_name

        # Load ID mapping
        index_dir = DATA_DIR / "colbert_index"
        mapping_path = index_dir / "id_mapping.json"

        if mapping_path.exists():
            with open(mapping_path) as f:
                self.id_mapping = json.load(f)
        else:
            self.id_mapping = {}

        # Load chunk metadata for results
        self.chunks_by_id = self._load_chunks()

        # Initialize searcher
        with Run().context(RunConfig(nranks=1, experiment="focus-group")):
            self.searcher = Searcher(index=index_name, checkpoint=checkpoint)

    def _load_chunks(self) -> Dict[str, Dict]:
        """Load all chunks and index by ID."""
        chunks_dir = DATA_DIR / "chunks_enriched"
        chunks_by_id = {}

        for fg_dir in sorted(chunks_dir.iterdir()):
            if fg_dir.is_dir():
                chunks_file = fg_dir / "all_chunks.json"
                if chunks_file.exists():
                    with open(chunks_file) as f:
                        chunks = json.load(f)
                        for chunk in chunks:
                            chunks_by_id[chunk["chunk_id"]] = chunk

        return chunks_by_id

    def retrieve(self, query: str, top_k: int = 5) -> List[ColBERTResult]:
        """Search using ColBERT."""
        # Search
        results = self.searcher.search(query, k=top_k)

        # Convert to ColBERTResult objects
        output = []
        for passage_id, rank, score in zip(*results):
            # Get chunk_id from mapping
            chunk_id = self.id_mapping.get(str(passage_id), f"unknown-{passage_id}")

            # Get chunk data
            chunk = self.chunks_by_id.get(chunk_id, {})
            content = chunk.get("content", chunk.get("content_original", ""))

            # Extract focus_group_id from chunk_id
            parts = chunk_id.split("-chunk-")
            focus_group_id = parts[0] if parts else chunk_id

            output.append(ColBERTResult(
                chunk_id=chunk_id,
                content=content,
                score=float(score),
                focus_group_id=focus_group_id,
                metadata=chunk.get("metadata", {})
            ))

        return output


def main():
    """Test ColBERT retrieval."""
    import argparse

    parser = argparse.ArgumentParser(description="ColBERT retrieval")
    parser.add_argument("query", nargs="?",
                        default="What did voters say about feeling abandoned by the party?")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--index", default="focus-group-colbert")

    args = parser.parse_args()

    print(f"Loading ColBERT index: {args.index}")
    retriever = ColBERTRetriever(index_name=args.index, verbose=True)

    print(f"\nQuery: {args.query}")
    print("=" * 60)

    results = retriever.retrieve(args.query, top_k=args.top_k)

    for i, r in enumerate(results):
        print(f"\n{i+1}. [{r.focus_group_id}] (score: {r.score:.3f})")
        print(f"   {r.content[:150]}...")


if __name__ == "__main__":
    main()
