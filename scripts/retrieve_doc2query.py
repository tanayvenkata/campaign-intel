#!/usr/bin/env python3
"""
Retriever for Doc2Query expanded chunks.
Uses the doc2query namespace in Pinecone V2 index.
"""

import sys
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import PINECONE_API_KEY
from scripts.retrieve_v2 import RetrievalResult


@dataclass
class Doc2QueryRetriever:
    """Retriever using Doc2Query expanded embeddings."""

    def __init__(
        self,
        use_router: bool = True,
        use_reranker: bool = False,
        verbose: bool = False
    ):
        from pinecone import Pinecone
        from sentence_transformers import SentenceTransformer

        self.verbose = verbose
        self.use_router = use_router
        self.use_reranker = use_reranker

        # Load embedding model
        self.model = SentenceTransformer("intfloat/e5-base-v2")

        # Connect to Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        self.index = pc.Index("focus-group-v2")

        # Load router if enabled
        if use_router:
            from scripts.retrieve_v2 import LLMRouter
            self.router = LLMRouter()
        else:
            self.router = None

        # Load reranker if enabled
        if use_reranker:
            from scripts.rerank import Reranker
            self.reranker = Reranker()
        else:
            self.reranker = None

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Search using Doc2Query namespace."""
        # Get filter from router
        filter_dict = None
        if self.router:
            focus_group_ids = self.router.route(query)
            if focus_group_ids:
                filter_dict = {"focus_group_id": {"$in": focus_group_ids}}

        # Embed query
        query_embedding = self.model.encode(
            f"query: {query}",
            normalize_embeddings=True
        )

        # Get more candidates if reranking
        search_k = top_k * 4 if self.use_reranker else top_k

        # Query doc2query namespace
        results = self.index.query(
            vector=query_embedding.tolist(),
            top_k=search_k,
            include_metadata=True,
            filter=filter_dict,
            namespace="doc2query"
        )

        # Convert to RetrievalResult
        output = []
        for match in results.matches:
            metadata = match.metadata or {}
            output.append(RetrievalResult(
                chunk_id=match.id,
                content=metadata.get("content", ""),
                score=match.score,
                focus_group_id=metadata.get("focus_group_id", ""),
                content_original=metadata.get("content", ""),
                participant=metadata.get("participant", ""),
                participant_profile=metadata.get("participant_profile", ""),
                section=metadata.get("section", ""),
                source_file=metadata.get("source_file", ""),
                line_number=metadata.get("line_number", 0)
            ))

        # Rerank if enabled
        if self.use_reranker and self.reranker and output:
            output = self.reranker.rerank(query, output, top_k=top_k)

        return output[:top_k]


def main():
    """Test Doc2Query retrieval."""
    import argparse

    parser = argparse.ArgumentParser(description="Doc2Query retrieval")
    parser.add_argument("query", nargs="?",
                        default="What did voters say about feeling abandoned by the party?")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-router", action="store_true")
    parser.add_argument("--rerank", action="store_true")

    args = parser.parse_args()

    print("Loading Doc2Query retriever...")
    retriever = Doc2QueryRetriever(
        use_router=not args.no_router,
        use_reranker=args.rerank,
        verbose=True
    )

    print(f"\nQuery: {args.query}")
    print("=" * 60)

    results = retriever.retrieve(args.query, top_k=args.top_k)

    for i, r in enumerate(results):
        print(f"\n{i+1}. [{r.focus_group_id}] (score: {r.score:.3f})")
        print(f"   {r.content[:150]}...")


if __name__ == "__main__":
    main()
