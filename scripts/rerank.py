#!/usr/bin/env python3
"""
Cross-Encoder Reranking for retrieval results.
Uses sentence-transformers CrossEncoder models.
"""

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))


class Reranker:
    """Cross-encoder reranker for retrieval results."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2"):
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, results: List, top_k: int = 5) -> List:
        """
        Rerank results using cross-encoder.

        Args:
            query: Search query
            results: List of RetrievalResult objects
            top_k: Number of results to return

        Returns:
            Reranked list of results
        """
        if not results:
            return []

        # Create query-document pairs
        pairs = [(query, r.content) for r in results]

        # Get scores from cross-encoder
        scores = self.model.predict(pairs)

        # Combine results with scores and sort
        scored_results = list(zip(results, scores))
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Return top_k
        return [r for r, s in scored_results[:top_k]]

    def rerank_with_scores(self, query: str, results: List, top_k: int = 5) -> List[tuple]:
        """
        Rerank and return results with their rerank scores.

        Returns:
            List of (result, rerank_score) tuples
        """
        if not results:
            return []

        pairs = [(query, r.content) for r in results]
        scores = self.model.predict(pairs)

        scored_results = list(zip(results, scores))
        scored_results.sort(key=lambda x: x[1], reverse=True)

        return scored_results[:top_k]


def main():
    """Test reranking."""
    import argparse
    from scripts.retrieve import FocusGroupRetrieverV2

    parser = argparse.ArgumentParser(description="Test reranking")
    parser.add_argument("query", nargs="?", default="What did voters say about feeling abandoned?")
    parser.add_argument("--model", default="cross-encoder/ms-marco-MiniLM-L6-v2")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=20)

    args = parser.parse_args()

    print(f"Loading reranker: {args.model}")
    reranker = Reranker(model_name=args.model)

    print("Loading retriever...")
    retriever = FocusGroupRetrieverV2(use_router=True, verbose=False)

    print(f"\nQuery: {args.query}")
    print(f"Getting top {args.candidates} candidates...")

    # Get candidates
    candidates = retriever.retrieve(args.query, top_k=args.candidates)

    print(f"\nBefore reranking (top {args.top_k}):")
    for i, r in enumerate(candidates[:args.top_k]):
        print(f"  {i+1}. [{r.focus_group_id}] {r.content[:80]}... (score: {r.score:.3f})")

    # Rerank
    print(f"\nReranking with {args.model}...")
    reranked = reranker.rerank_with_scores(args.query, candidates, top_k=args.top_k)

    print(f"\nAfter reranking (top {args.top_k}):")
    for i, (r, score) in enumerate(reranked):
        print(f"  {i+1}. [{r.focus_group_id}] {r.content[:80]}... (rerank: {score:.3f})")


if __name__ == "__main__":
    main()
