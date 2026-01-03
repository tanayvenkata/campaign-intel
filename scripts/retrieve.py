#!/usr/bin/env python3
"""
Retrieve relevant focus group chunks using hybrid search (dense + BM25).
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import (
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    DATA_DIR,
    FOCUS_GROUPS_DIR,
)

# Lazy imports
openai = None
pinecone = None
BM25Encoder = None


def load_dependencies():
    """Load optional dependencies."""
    global openai, pinecone, BM25Encoder

    try:
        import openai as _openai
        openai = _openai
    except ImportError:
        raise ImportError("openai not installed. Run: pip install openai")

    try:
        from pinecone import Pinecone
        pinecone = Pinecone
    except ImportError:
        raise ImportError("pinecone not installed. Run: pip install pinecone-client")

    try:
        from pinecone_text.sparse import BM25Encoder as _BM25Encoder
        BM25Encoder = _BM25Encoder
    except ImportError:
        raise ImportError("pinecone-text not installed. Run: pip install pinecone-text")


@dataclass
class RetrievalResult:
    """Single retrieval result."""
    chunk_id: str
    score: float
    content: str
    focus_group_id: str
    participant: str
    participant_profile: str
    section: str
    source_file: str
    line_number: int


@dataclass
class GroupedResults:
    """Results grouped by focus group with metadata."""
    focus_group_id: str
    focus_group_metadata: Dict
    chunks: List[RetrievalResult]


class FocusGroupRetriever:
    """Hybrid retrieval for focus group chunks."""

    def __init__(self):
        load_dependencies()

        self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.pc = pinecone(api_key=PINECONE_API_KEY)
        self.index = self.pc.Index(PINECONE_INDEX_NAME)

        # Load BM25 encoder
        bm25_path = DATA_DIR / "bm25_encoder.json"
        if not bm25_path.exists():
            raise FileNotFoundError(f"BM25 encoder not found at {bm25_path}. Run embed.py first.")
        self.bm25_encoder = BM25Encoder.default()
        self.bm25_encoder.load(str(bm25_path))

        # Cache for focus group metadata
        self._fg_metadata_cache: Dict[str, Dict] = {}

    def _get_dense_embedding(self, query: str) -> List[float]:
        """Get dense embedding for query."""
        response = self.openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[query]
        )
        return response.data[0].embedding

    def _get_sparse_vector(self, query: str) -> Dict:
        """Get BM25 sparse vector for query."""
        sparse = self.bm25_encoder.encode_queries([query])[0]
        return {
            "indices": sparse["indices"],
            "values": sparse["values"]
        }

    def _load_focus_group_metadata(self, fg_id: str) -> Dict:
        """Load focus group metadata from file."""
        if fg_id in self._fg_metadata_cache:
            return self._fg_metadata_cache[fg_id]

        fg_file = FOCUS_GROUPS_DIR / f"{fg_id}.json"
        if fg_file.exists():
            with open(fg_file) as f:
                metadata = json.load(f)
                self._fg_metadata_cache[fg_id] = metadata
                return metadata

        return {}

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        alpha: float = 0.5,
        filter_focus_groups: Optional[List[str]] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks using hybrid search.

        Args:
            query: Search query
            top_k: Number of results to return
            alpha: Balance between dense (1.0) and sparse (0.0). Default 0.5.
            filter_focus_groups: Optional list of focus group IDs to filter by

        Returns:
            List of RetrievalResult objects
        """
        # Get embeddings
        dense_vector = self._get_dense_embedding(query)
        sparse_vector = self._get_sparse_vector(query)

        # Build filter if specified
        filter_dict = None
        if filter_focus_groups:
            filter_dict = {"focus_group_id": {"$in": filter_focus_groups}}

        # Query Pinecone with hybrid search
        results = self.index.query(
            vector=dense_vector,
            sparse_vector=sparse_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict
        )

        # Convert to RetrievalResult objects
        retrieval_results = []
        for match in results.matches:
            meta = match.metadata
            retrieval_results.append(RetrievalResult(
                chunk_id=match.id,
                score=match.score,
                content=meta.get("content", ""),
                focus_group_id=meta.get("focus_group_id", ""),
                participant=meta.get("participant", ""),
                participant_profile=meta.get("participant_profile", ""),
                section=meta.get("section", ""),
                source_file=meta.get("source_file", ""),
                line_number=meta.get("line_number", 0),
            ))

        return retrieval_results

    def retrieve_grouped(
        self,
        query: str,
        top_k: int = 10,
        alpha: float = 0.5,
        filter_focus_groups: Optional[List[str]] = None
    ) -> List[GroupedResults]:
        """
        Retrieve and group results by focus group.
        Includes focus group metadata (moderator notes) as header context.
        """
        results = self.retrieve(query, top_k, alpha, filter_focus_groups)

        # Group by focus group
        groups: Dict[str, List[RetrievalResult]] = {}
        for result in results:
            fg_id = result.focus_group_id
            if fg_id not in groups:
                groups[fg_id] = []
            groups[fg_id].append(result)

        # Create GroupedResults with metadata
        grouped = []
        for fg_id, chunks in groups.items():
            metadata = self._load_focus_group_metadata(fg_id)
            grouped.append(GroupedResults(
                focus_group_id=fg_id,
                focus_group_metadata=metadata,
                chunks=chunks
            ))

        # Sort by highest scoring chunk in each group
        grouped.sort(key=lambda g: max(c.score for c in g.chunks), reverse=True)

        return grouped


def format_results_for_display(grouped_results: List[GroupedResults]) -> str:
    """Format grouped results for display (Rachel's Option C format)."""
    output = []

    for group in grouped_results:
        meta = group.focus_group_metadata

        # Header with focus group info
        header = f"\n{'='*60}\n"
        header += f"## {meta.get('location', group.focus_group_id)}\n"
        header += f"**{meta.get('race_name', '')}** | {meta.get('date', '')}\n"
        header += f"Participants: {meta.get('participant_summary', '')}\n"

        # Moderator notes summary if available
        mod_notes = meta.get("moderator_notes", {})
        if mod_notes.get("key_themes"):
            header += f"\n**Key Themes:** {', '.join(mod_notes['key_themes'])}\n"
        if mod_notes.get("vote_intent_summary"):
            header += f"**Vote Intent:** {mod_notes['vote_intent_summary']}\n"

        header += f"{'='*60}\n"
        output.append(header)

        # Quotes
        for chunk in group.chunks:
            quote = f"\n**{chunk.participant}** ({chunk.participant_profile}):\n"
            quote += f"> \"{chunk.content}\"\n"
            quote += f"_[{chunk.source_file}:{chunk.line_number}]_\n"
            output.append(quote)

    return "".join(output)


def main():
    """Interactive retrieval demo."""
    import argparse

    parser = argparse.ArgumentParser(description="Focus Group Retrieval")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    parser.add_argument("--focus-groups", nargs="+", help="Filter to specific focus groups")
    parser.add_argument("--raw", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    retriever = FocusGroupRetriever()

    if args.query:
        # Single query mode
        grouped = retriever.retrieve_grouped(
            args.query,
            top_k=args.top_k,
            filter_focus_groups=args.focus_groups
        )

        if args.raw:
            # Output as JSON
            output = []
            for group in grouped:
                output.append({
                    "focus_group_id": group.focus_group_id,
                    "metadata": group.focus_group_metadata,
                    "chunks": [
                        {
                            "chunk_id": c.chunk_id,
                            "score": c.score,
                            "content": c.content,
                            "participant": c.participant,
                            "participant_profile": c.participant_profile,
                            "section": c.section,
                            "line_number": c.line_number,
                        }
                        for c in group.chunks
                    ]
                })
            print(json.dumps(output, indent=2))
        else:
            # Formatted display
            print(format_results_for_display(grouped))

    else:
        # Interactive mode
        print("Focus Group Retrieval (type 'quit' to exit)")
        print("-" * 40)

        while True:
            query = input("\nQuery: ").strip()
            if query.lower() in ("quit", "exit", "q"):
                break
            if not query:
                continue

            grouped = retriever.retrieve_grouped(query, top_k=args.top_k)
            print(format_results_for_display(grouped))


if __name__ == "__main__":
    main()
