"""
Hybrid retriever combining dense (BGE-M3) and sparse (BM25) signals.
Uses Reciprocal Rank Fusion (RRF) to merge results.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.retrieve import (
    FocusGroupRetrieverV2,
    RetrievalResult,
    GroupedResults,
    LLMRouter,
)
from scripts.retrieval.bm25 import BM25Retriever
from eval.config import DATA_DIR


class FusionStrategy(Enum):
    RRF = "rrf"  # Reciprocal Rank Fusion (recommended)
    WEIGHTED = "weighted"  # Weighted linear combination


@dataclass
class HybridResult:
    """Extended retrieval result with hybrid scoring info."""
    chunk_id: str
    score: float  # Fused score
    dense_score: float
    bm25_score: float
    dense_rank: int
    bm25_rank: int
    content: str
    content_original: str
    focus_group_id: str
    participant: str
    participant_profile: str
    section: str
    source_file: str
    line_number: int
    preceding_moderator_q: str = ""

    def to_retrieval_result(self) -> RetrievalResult:
        """Convert to standard RetrievalResult for API compatibility."""
        return RetrievalResult(
            chunk_id=self.chunk_id,
            score=self.score,
            content=self.content,
            content_original=self.content_original,
            focus_group_id=self.focus_group_id,
            participant=self.participant,
            participant_profile=self.participant_profile,
            section=self.section,
            source_file=self.source_file,
            line_number=self.line_number,
            preceding_moderator_q=self.preceding_moderator_q,
        )


class HybridFocusGroupRetriever:
    """
    Hybrid retriever that fuses dense (BGE-M3) and BM25 results.

    Uses RRF (Reciprocal Rank Fusion) by default for score-agnostic fusion.
    Provides same interface as FocusGroupRetrieverV2 for drop-in replacement.
    """

    def __init__(
        self,
        use_router: bool = True,
        use_reranker: bool = False,
        fusion_strategy: FusionStrategy = FusionStrategy.RRF,
        rrf_k: int = 60,
        dense_weight: float = 0.6,
        bm25_weight: float = 0.4,
        verbose: bool = False,
    ):
        """
        Initialize hybrid retriever.

        Args:
            use_router: Whether to use LLM router for focus group filtering
            use_reranker: Whether to use cross-encoder reranking after fusion
            fusion_strategy: RRF (default) or WEIGHTED
            rrf_k: RRF constant (default 60, standard value)
            dense_weight: Weight for dense scores (for WEIGHTED strategy)
            bm25_weight: Weight for BM25 scores (for WEIGHTED strategy)
            verbose: Print debug info
        """
        self.verbose = verbose
        self.fusion_strategy = fusion_strategy
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight

        # Initialize dense retriever (no reranker - we'll rerank after fusion)
        if verbose:
            print("Initializing dense retriever...")
        self.dense_retriever = FocusGroupRetrieverV2(
            use_router=use_router,
            use_reranker=False,  # Rerank after fusion
            verbose=verbose,
        )

        # Initialize BM25 retriever (singleton, loads once)
        if verbose:
            print("Initializing BM25 retriever...")
        self.bm25_retriever = BM25Retriever(verbose=verbose)

        # Share router from dense retriever
        self.router = self.dense_retriever.router
        self.use_router = use_router

        # Optional reranker
        self.use_reranker = use_reranker
        if use_reranker:
            from scripts.retrieval.base import SharedResources
            self.reranker = SharedResources.get_reranker_model()
        else:
            self.reranker = None

    def _rrf_score(self, rank: int) -> float:
        """Calculate RRF score for a given rank (1-indexed)."""
        return 1.0 / (self.rrf_k + rank)

    def _fuse_results(
        self,
        dense_results: List[RetrievalResult],
        bm25_results: List,  # BM25Result
    ) -> List[HybridResult]:
        """
        Fuse dense and BM25 results using RRF or weighted combination.

        High-confidence BM25-only boost: When BM25 strongly signals a result
        (top 5 with score > 1.5x median) that dense missed (router excluded it),
        we use the BM25 rank as a virtual dense rank instead of max_dense_rank.
        This prevents the router from killing good keyword matches.

        Args:
            dense_results: Results from dense retriever
            bm25_results: Results from BM25 retriever

        Returns:
            Fused results sorted by hybrid score
        """
        # Build lookup maps with ranks (1-indexed)
        dense_map = {}
        for rank, r in enumerate(dense_results, 1):
            dense_map[r.chunk_id] = (rank, r)

        bm25_map = {}
        for rank, r in enumerate(bm25_results, 1):
            bm25_map[r.chunk_id] = (rank, r)

        # Get all unique chunk IDs
        all_ids = set(dense_map.keys()) | set(bm25_map.keys())

        # Calculate max ranks for missing items
        max_dense_rank = len(dense_results) + 1
        max_bm25_rank = len(bm25_results) + 1

        # For weighted fusion, we need to normalize BM25 scores
        max_bm25_score = max((r.bm25_score for r in bm25_results), default=1.0) or 1.0

        # Calculate median BM25 score for high-confidence detection
        if bm25_results:
            sorted_scores = sorted([r.bm25_score for r in bm25_results], reverse=True)
            median_bm25 = sorted_scores[len(sorted_scores) // 2]
        else:
            median_bm25 = 0.0

        fused = []
        for chunk_id in all_ids:
            # Get dense info
            dense_rank, dense_result = dense_map.get(chunk_id, (max_dense_rank, None))
            dense_score = dense_result.score if dense_result else 0.0

            # Get BM25 info
            bm25_rank, bm25_result = bm25_map.get(chunk_id, (max_bm25_rank, None))
            bm25_score = bm25_result.bm25_score if bm25_result else 0.0

            # High-confidence BM25-only boost:
            # If BM25 found this (top 5, score > 1.5x median) but dense missed it,
            # use BM25 rank as virtual dense rank instead of max penalty
            virtual_dense_rank = dense_rank
            if dense_result is None and bm25_result is not None:
                if bm25_rank <= 5 and bm25_score > median_bm25 * 1.5:
                    # Strong BM25 signal that router missed - boost it
                    virtual_dense_rank = bm25_rank
                    if self.verbose:
                        print(f"  [BM25 boost] {chunk_id[:40]}... rank {bm25_rank}, score {bm25_score:.2f}")

            # Calculate fused score
            if self.fusion_strategy == FusionStrategy.RRF:
                fused_score = self._rrf_score(virtual_dense_rank) + self._rrf_score(bm25_rank)
            else:  # WEIGHTED
                normalized_bm25 = bm25_score / max_bm25_score
                fused_score = (self.dense_weight * dense_score +
                               self.bm25_weight * normalized_bm25)

            # Get metadata from whichever result we have
            source = dense_result if dense_result else bm25_result

            fused.append(HybridResult(
                chunk_id=chunk_id,
                score=fused_score,
                dense_score=dense_score,
                bm25_score=bm25_score,
                dense_rank=virtual_dense_rank,  # May be boosted
                bm25_rank=bm25_rank,
                content=source.content if hasattr(source, 'content') else getattr(source, 'content', ''),
                content_original=source.content_original if hasattr(source, 'content_original') else getattr(source, 'content_original', ''),
                focus_group_id=source.focus_group_id if hasattr(source, 'focus_group_id') else getattr(source, 'focus_group_id', ''),
                participant=source.participant if hasattr(source, 'participant') else getattr(source, 'participant', ''),
                participant_profile=source.participant_profile if hasattr(source, 'participant_profile') else getattr(source, 'participant_profile', ''),
                section=source.section if hasattr(source, 'section') else getattr(source, 'section', ''),
                source_file=source.source_file if hasattr(source, 'source_file') else getattr(source, 'source_file', ''),
                line_number=source.line_number if hasattr(source, 'line_number') else getattr(source, 'line_number', 0),
                preceding_moderator_q=source.preceding_moderator_q if hasattr(source, 'preceding_moderator_q') else getattr(source, 'preceding_moderator_q', ''),
            ))

        # Sort by fused score descending
        fused.sort(key=lambda x: x.score, reverse=True)
        return fused

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_focus_groups: Optional[List[str]] = None,
        candidate_multiplier: int = 4,
    ) -> List[RetrievalResult]:
        """
        Hybrid retrieval with score fusion.

        Args:
            query: Search query
            top_k: Number of final results
            filter_focus_groups: Optional list of FG IDs to filter (only applies to dense)
            candidate_multiplier: Get this many more candidates from each retriever

        Returns:
            List of RetrievalResult sorted by hybrid score
        """
        candidate_k = top_k * candidate_multiplier

        # Get dense results (respects router/filter for focused semantic search)
        if self.verbose:
            print(f"Dense retrieval (top_k={candidate_k}, filtered={filter_focus_groups is not None})...")
        dense_results = self.dense_retriever.retrieve(
            query,
            top_k=candidate_k,
            filter_focus_groups=filter_focus_groups,
        )

        # Get BM25 results (searches ALL FGs - fast enough, catches router misses)
        if self.verbose:
            print(f"BM25 retrieval (top_k={candidate_k}, searching ALL FGs)...")
        bm25_results = self.bm25_retriever.retrieve(
            query,
            top_k=candidate_k,
            filter_focus_groups=None,  # Always search all - BM25 is fast
        )

        if self.verbose:
            print(f"Fusing {len(dense_results)} dense + {len(bm25_results)} BM25 results...")

        # Fuse results
        fused = self._fuse_results(dense_results, bm25_results)

        # Optional reranking
        if self.use_reranker and self.reranker and fused:
            if self.verbose:
                print(f"Reranking top {min(len(fused), top_k * 2)} results...")
            # Convert to RetrievalResult for reranker
            to_rerank = [f.to_retrieval_result() for f in fused[:top_k * 2]]
            reranked = self.reranker.rerank(query, to_rerank, top_k=top_k)
            return reranked

        # Convert to RetrievalResult and return top_k
        return [f.to_retrieval_result() for f in fused[:top_k]]

    def retrieve_per_focus_group(
        self,
        query: str,
        top_k_per_fg: int = 5,
        score_threshold: float = 0.50,
        filter_focus_groups: Optional[List[str]] = None,
    ) -> Dict[str, List[RetrievalResult]]:
        """
        Per-focus-group hybrid retrieval.

        Fuses dense and BM25 results within each focus group.

        Args:
            query: Search query
            top_k_per_fg: Max results per focus group
            score_threshold: Minimum hybrid score to include
            filter_focus_groups: Optional list of FG IDs

        Returns:
            Dict mapping focus_group_id -> list of results
        """
        # Determine which FGs to search
        if filter_focus_groups:
            fg_ids = filter_focus_groups
        elif self.use_router and self.router:
            fg_ids = self.router.route(query)
            if fg_ids is None:
                fg_ids = self.router._get_all_fg_ids()
            if self.verbose:
                print(f"Router selected {len(fg_ids)} focus groups")
        else:
            # Fallback to all FGs from manifest
            import json
            manifest_file = DATA_DIR / "manifest.json"
            with open(manifest_file) as f:
                data = json.load(f)
            fg_ids = [fg["focus_group_id"] for fg in data["focus_groups"]]

        # Get candidates from both retrievers (more than needed)
        candidate_k = top_k_per_fg * 6 * len(fg_ids)  # Enough for all FGs

        if self.verbose:
            print(f"Getting candidates from dense (filtered) and BM25 (all FGs)...")

        # Dense respects router filter
        dense_results = self.dense_retriever.retrieve(
            query,
            top_k=candidate_k,
            filter_focus_groups=fg_ids,
        )

        # BM25 searches ALL FGs to catch router misses (fast enough)
        bm25_results = self.bm25_retriever.retrieve(
            query,
            top_k=candidate_k,
            filter_focus_groups=None,  # Search all - catches entities router doesn't recognize
        )

        # Fuse all results first
        fused = self._fuse_results(dense_results, bm25_results)

        # Group by focus group and apply threshold
        # Note: We don't filter by fg_ids here - BM25 may have found good results
        # in FGs the router didn't select (e.g., "Republic Steel" → Cleveland)
        results_by_fg: Dict[str, List[RetrievalResult]] = {}

        for hybrid_result in fused:
            fg_id = hybrid_result.focus_group_id

            # Apply score threshold (RRF scores are small, so use relative threshold)
            if self.fusion_strategy == FusionStrategy.RRF:
                # RRF max score for top-1 in both = 2/(k+1) ≈ 0.033 for k=60
                # Use threshold relative to that
                min_score = score_threshold * 0.01  # e.g., 0.50 * 0.01 = 0.005
            else:
                min_score = score_threshold

            if hybrid_result.score < min_score:
                continue

            if fg_id not in results_by_fg:
                results_by_fg[fg_id] = []

            if len(results_by_fg[fg_id]) < top_k_per_fg:
                results_by_fg[fg_id].append(hybrid_result.to_retrieval_result())

        if self.verbose:
            for fg_id, results in results_by_fg.items():
                if results:
                    print(f"  {fg_id}: {len(results)} results (top score: {results[0].score:.4f})")

        return results_by_fg

    def retrieve_grouped(
        self,
        query: str,
        top_k: int = 5,
        filter_focus_groups: Optional[List[str]] = None,
        per_focus_group: bool = False,
        score_threshold: float = 0.50,
    ) -> List[GroupedResults]:
        """
        Retrieve and group results by focus group.

        Args:
            query: Search query
            top_k: Number of results (global or per-FG depending on mode)
            filter_focus_groups: Optional list of FG IDs
            per_focus_group: If True, use per-FG retrieval
            score_threshold: Minimum score (for per-FG mode)

        Returns:
            List of GroupedResults sorted by top score per group
        """
        if per_focus_group:
            results_by_fg = self.retrieve_per_focus_group(
                query,
                top_k_per_fg=min(top_k, 5),
                score_threshold=score_threshold,
                filter_focus_groups=filter_focus_groups,
            )
        else:
            # Global retrieval, then group
            results = self.retrieve(
                query,
                top_k=top_k * 5,  # Get more, then group
                filter_focus_groups=filter_focus_groups,
            )

            results_by_fg: Dict[str, List[RetrievalResult]] = {}
            for r in results:
                if r.focus_group_id not in results_by_fg:
                    results_by_fg[r.focus_group_id] = []
                if len(results_by_fg[r.focus_group_id]) < top_k:
                    results_by_fg[r.focus_group_id].append(r)

        # Convert to GroupedResults
        grouped = []
        for fg_id, chunks in results_by_fg.items():
            if not chunks:
                continue

            # Load FG metadata
            fg_metadata = self.dense_retriever._load_focus_group_metadata(fg_id)

            grouped.append(GroupedResults(
                focus_group_id=fg_id,
                focus_group_metadata=fg_metadata,
                chunks=chunks,
            ))

        # Sort by top score in each group
        grouped.sort(key=lambda g: g.chunks[0].score if g.chunks else 0, reverse=True)

        return grouped


if __name__ == "__main__":
    # Quick comparison test
    print("=" * 60)
    print("HYBRID vs DENSE-ONLY COMPARISON")
    print("=" * 60)

    # Initialize retrievers
    print("\nInitializing retrievers...")
    dense = FocusGroupRetrieverV2(use_router=True, verbose=False)
    hybrid = HybridFocusGroupRetriever(use_router=True, verbose=False)

    test_queries = [
        ("P7 unions", "keyword-heavy"),
        ("Republic Steel", "keyword-heavy"),
        ("economic anxiety", "semantic"),
        ("feeling abandoned by the party", "semantic"),
    ]

    for query, category in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: '{query}' ({category})")
        print("=" * 60)

        # Dense results
        dense_results = dense.retrieve(query, top_k=5)
        print(f"\nDENSE (top 3):")
        for i, r in enumerate(dense_results[:3], 1):
            preview = r.content_original[:60] + "..." if len(r.content_original) > 60 else r.content_original
            print(f"  {i}. [{r.score:.3f}] {r.focus_group_id} - {r.participant}")
            print(f"     {preview}")

        # Hybrid results
        hybrid_results = hybrid.retrieve(query, top_k=5)
        print(f"\nHYBRID (top 3):")
        for i, r in enumerate(hybrid_results[:3], 1):
            preview = r.content_original[:60] + "..." if len(r.content_original) > 60 else r.content_original
            print(f"  {i}. [{r.score:.4f}] {r.focus_group_id} - {r.participant}")
            print(f"     {preview}")
