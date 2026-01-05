"""
BM25 retriever for hybrid search.
Loads all focus group chunks into memory and indexes with BM25.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rank_bm25 import BM25Okapi
from eval.config import DATA_DIR


@dataclass
class BM25Result:
    """Single BM25 retrieval result."""
    chunk_id: str
    bm25_score: float
    content: str
    content_original: str
    focus_group_id: str
    participant: str
    participant_profile: str
    section: str
    source_file: str
    line_number: int
    preceding_moderator_q: str = ""


class BM25Retriever:
    """
    In-memory BM25 retriever for focus group chunks.

    Indexes content_original + participant_profile for keyword matching.
    Supports focus group filtering to match dense retriever behavior.
    """

    _instance = None
    _chunks = None
    _bm25 = None
    _chunk_index = None
    _tokenized_corpus = None
    _initialized = False

    def __new__(cls, verbose: bool = False):
        """Singleton pattern - BM25 index is expensive to build."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._verbose = verbose
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, verbose: bool = False):
        if self._initialized:
            return

        self.verbose = getattr(self, '_verbose', verbose)
        self._load_and_index()
        self._initialized = True

    def _load_and_index(self):
        """Load all chunks and build BM25 index."""
        chunks_dir = DATA_DIR / "chunks_enriched"

        if self.verbose:
            print(f"Loading chunks from {chunks_dir}...")

        # Load all chunks from all focus groups
        all_chunks = []
        for fg_dir in sorted(chunks_dir.iterdir()):
            if not fg_dir.is_dir():
                continue
            chunks_file = fg_dir / "all_chunks.json"
            if chunks_file.exists():
                with open(chunks_file) as f:
                    chunks = json.load(f)
                    all_chunks.extend(chunks)

        self._chunks = all_chunks
        self._chunk_index = {c["chunk_id"]: c for c in all_chunks}

        if self.verbose:
            print(f"Loaded {len(all_chunks)} chunks from {len(list(chunks_dir.iterdir()))} focus groups")

        # Build BM25 index
        # Index content_original + participant_profile for keyword matching
        corpus = []
        for chunk in all_chunks:
            text = self._get_indexable_text(chunk)
            corpus.append(text)

        # Tokenize corpus (simple whitespace + lowercase)
        self._tokenized_corpus = [self._tokenize(doc) for doc in corpus]
        self._bm25 = BM25Okapi(self._tokenized_corpus)

        if self.verbose:
            print(f"Built BM25 index with {len(corpus)} documents")

    def _get_indexable_text(self, chunk: Dict) -> str:
        """Combine fields for BM25 indexing."""
        parts = []

        # Primary: raw quote text
        if chunk.get("content_original"):
            parts.append(chunk["content_original"])

        # Secondary: participant profile (demographics, location, etc.)
        if chunk.get("participant_profile"):
            parts.append(chunk["participant_profile"])

        # Include participant ID for exact matching (e.g., "P7")
        if chunk.get("participant"):
            parts.append(chunk["participant"])

        return " ".join(parts)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase, split on whitespace and punctuation."""
        import re
        # Lowercase and split on non-alphanumeric (keeping apostrophes for contractions)
        tokens = re.findall(r"[a-z0-9']+", text.lower())
        return tokens

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filter_focus_groups: Optional[List[str]] = None
    ) -> List[BM25Result]:
        """
        Retrieve chunks using BM25 scoring.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_focus_groups: Optional list of focus group IDs to filter to

        Returns:
            List of BM25Result sorted by score descending
        """
        # Tokenize query
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        # Get BM25 scores for all documents
        scores = self._bm25.get_scores(query_tokens)

        # Pair chunks with scores and filter
        results = []
        for idx, (chunk, score) in enumerate(zip(self._chunks, scores)):
            # Apply focus group filter if specified
            if filter_focus_groups and chunk["focus_group_id"] not in filter_focus_groups:
                continue

            # Skip zero scores
            if score <= 0:
                continue

            results.append((chunk, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Convert to BM25Result objects
        return [
            BM25Result(
                chunk_id=chunk["chunk_id"],
                bm25_score=score,
                content=chunk.get("content", ""),
                content_original=chunk.get("content_original", ""),
                focus_group_id=chunk["focus_group_id"],
                participant=chunk.get("participant", ""),
                participant_profile=chunk.get("participant_profile", ""),
                section=chunk.get("section", ""),
                source_file=chunk.get("source_file", ""),
                line_number=chunk.get("line_number", 0),
                preceding_moderator_q=chunk.get("preceding_moderator_q", ""),
            )
            for chunk, score in results[:top_k]
        ]

    def get_chunk(self, chunk_id: str) -> Optional[Dict]:
        """Get chunk by ID."""
        return self._chunk_index.get(chunk_id)

    @property
    def num_chunks(self) -> int:
        """Total number of indexed chunks."""
        return len(self._chunks) if self._chunks else 0

    @classmethod
    def reset(cls):
        """Reset singleton (useful for testing)."""
        cls._instance = None
        cls._chunks = None
        cls._bm25 = None
        cls._chunk_index = None
        cls._tokenized_corpus = None


if __name__ == "__main__":
    # Quick test
    retriever = BM25Retriever(verbose=True)

    print("\n" + "="*60)
    print("Testing BM25 retrieval")
    print("="*60)

    test_queries = [
        "P7 unions",
        "Republic Steel",
        "retired steelworker",
        "Parma",
        "economic anxiety",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = retriever.retrieve(query, top_k=3)
        for i, r in enumerate(results, 1):
            preview = r.content_original[:80] + "..." if len(r.content_original) > 80 else r.content_original
            print(f"  {i}. [{r.bm25_score:.2f}] {r.focus_group_id} - {r.participant}")
            print(f"     {preview}")
