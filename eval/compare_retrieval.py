#!/usr/bin/env python3
"""
A/B comparison of dense-only vs hybrid retrieval.

Compares FocusGroupRetrieverV2 (dense) against HybridFocusGroupRetriever
on a set of test queries and outputs detailed comparison metrics.

Usage:
    python eval/compare_retrieval.py                    # Run all test queries
    python eval/compare_retrieval.py --query "P7"       # Single query
    python eval/compare_retrieval.py --no-router        # Disable LLM router (search all FGs)
"""

import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from collections import defaultdict
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.retrieve import FocusGroupRetrieverV2, RetrievalResult
from scripts.retrieval.hybrid import HybridFocusGroupRetriever
from scripts.retrieval.bm25 import BM25Retriever


@dataclass
class QueryResult:
    """Results for a single query comparison."""
    query_id: str
    query: str
    category: str

    # Dense results
    dense_results: List[RetrievalResult] = field(default_factory=list)
    dense_time_ms: float = 0.0

    # Hybrid results
    hybrid_results: List[RetrievalResult] = field(default_factory=list)
    hybrid_time_ms: float = 0.0

    # BM25-only results (for debugging)
    bm25_results: List = field(default_factory=list)

    # Expected data
    expected_fgs: Optional[List[str]] = None
    expected_participant: Optional[str] = None
    expected_keywords: Optional[List[str]] = None

    # Computed metrics
    dense_found_expected_fg: bool = False
    hybrid_found_expected_fg: bool = False
    dense_found_expected_participant: bool = False
    hybrid_found_expected_participant: bool = False
    dense_found_keywords: bool = False
    hybrid_found_keywords: bool = False


def check_expected_fg(results: List[RetrievalResult], expected_fgs: Optional[List[str]]) -> bool:
    """Check if any expected FG appears in top-5 results."""
    if not expected_fgs:
        return True  # No expectation = pass

    result_fgs = {r.focus_group_id for r in results[:5]}
    return bool(result_fgs & set(expected_fgs))


def check_expected_participant(results: List[RetrievalResult], expected_participant: Optional[str]) -> bool:
    """Check if expected participant appears in top-5 results."""
    if not expected_participant:
        return True

    return any(r.participant == expected_participant for r in results[:5])


def check_keywords(results: List[RetrievalResult], keywords: Optional[List[str]]) -> bool:
    """Check if any keyword appears in top-5 result content."""
    if not keywords:
        return True

    for r in results[:5]:
        text = (r.content_original + " " + r.participant_profile).lower()
        for kw in keywords:
            if kw.lower() in text:
                return True
    return False


def format_result(r: RetrievalResult, rank: int) -> str:
    """Format a single result for display."""
    preview = r.content_original[:60] + "..." if len(r.content_original) > 60 else r.content_original
    return f"  {rank}. [{r.score:.4f}] {r.focus_group_id} - {r.participant}\n     {preview}"


def run_comparison(
    queries: List[Dict],
    use_router: bool = True,
    verbose: bool = False,
) -> List[QueryResult]:
    """Run comparison on all queries."""

    print("Initializing retrievers...")
    dense = FocusGroupRetrieverV2(use_router=use_router, verbose=False)
    hybrid = HybridFocusGroupRetriever(use_router=use_router, verbose=False)
    bm25 = BM25Retriever(verbose=False)

    results = []

    for q in queries:
        query_id = q["id"]
        query = q["query"]
        category = q["category"]

        if verbose:
            print(f"\nProcessing: {query_id} - '{query}'")

        qr = QueryResult(
            query_id=query_id,
            query=query,
            category=category,
            expected_fgs=q.get("expected_focus_groups"),
            expected_participant=q.get("expected_participant"),
            expected_keywords=q.get("expected_keywords"),
        )

        # Run dense retrieval
        start = time.time()
        qr.dense_results = dense.retrieve(query, top_k=10)
        qr.dense_time_ms = (time.time() - start) * 1000

        # Run hybrid retrieval
        start = time.time()
        qr.hybrid_results = hybrid.retrieve(query, top_k=10)
        qr.hybrid_time_ms = (time.time() - start) * 1000

        # Run BM25-only for debugging
        qr.bm25_results = bm25.retrieve(query, top_k=10)

        # Check expectations
        qr.dense_found_expected_fg = check_expected_fg(qr.dense_results, qr.expected_fgs)
        qr.hybrid_found_expected_fg = check_expected_fg(qr.hybrid_results, qr.expected_fgs)
        qr.dense_found_expected_participant = check_expected_participant(qr.dense_results, qr.expected_participant)
        qr.hybrid_found_expected_participant = check_expected_participant(qr.hybrid_results, qr.expected_participant)
        qr.dense_found_keywords = check_keywords(qr.dense_results, qr.expected_keywords)
        qr.hybrid_found_keywords = check_keywords(qr.hybrid_results, qr.expected_keywords)

        results.append(qr)

    return results


def print_detailed_results(results: List[QueryResult]):
    """Print detailed per-query results."""

    for qr in results:
        print("\n" + "=" * 70)
        print(f"Query: '{qr.query}'")
        print(f"ID: {qr.query_id} | Category: {qr.category}")
        if qr.expected_fgs:
            print(f"Expected FGs: {qr.expected_fgs}")
        if qr.expected_participant:
            print(f"Expected participant: {qr.expected_participant}")
        if qr.expected_keywords:
            print(f"Expected keywords: {qr.expected_keywords}")
        print("=" * 70)

        # Dense results
        print(f"\nDENSE-ONLY ({qr.dense_time_ms:.0f}ms):")
        for i, r in enumerate(qr.dense_results[:5], 1):
            print(format_result(r, i))

        fg_check = "✓" if qr.dense_found_expected_fg else "✗"
        participant_check = "✓" if qr.dense_found_expected_participant else "✗"
        keyword_check = "✓" if qr.dense_found_keywords else "✗"
        print(f"\n  Expected FG: {fg_check} | Participant: {participant_check} | Keywords: {keyword_check}")

        # Hybrid results
        print(f"\nHYBRID ({qr.hybrid_time_ms:.0f}ms):")
        for i, r in enumerate(qr.hybrid_results[:5], 1):
            print(format_result(r, i))

        fg_check = "✓" if qr.hybrid_found_expected_fg else "✗"
        participant_check = "✓" if qr.hybrid_found_expected_participant else "✗"
        keyword_check = "✓" if qr.hybrid_found_keywords else "✗"
        print(f"\n  Expected FG: {fg_check} | Participant: {participant_check} | Keywords: {keyword_check}")

        # BM25-only (for debugging keyword queries)
        if qr.category == "keyword-heavy":
            print(f"\nBM25-ONLY (debug):")
            for i, r in enumerate(qr.bm25_results[:3], 1):
                preview = r.content_original[:60] + "..." if len(r.content_original) > 60 else r.content_original
                print(f"  {i}. [{r.bm25_score:.2f}] {r.focus_group_id} - {r.participant}")
                print(f"     {preview}")

        # Verdict
        dense_score = sum([qr.dense_found_expected_fg, qr.dense_found_expected_participant, qr.dense_found_keywords])
        hybrid_score = sum([qr.hybrid_found_expected_fg, qr.hybrid_found_expected_participant, qr.hybrid_found_keywords])

        if hybrid_score > dense_score:
            print(f"\n  VERDICT: HYBRID WINS ({hybrid_score}/3 vs {dense_score}/3)")
        elif dense_score > hybrid_score:
            print(f"\n  VERDICT: DENSE WINS ({dense_score}/3 vs {hybrid_score}/3)")
        else:
            print(f"\n  VERDICT: TIE ({dense_score}/3)")


def print_summary(results: List[QueryResult]):
    """Print summary statistics."""

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    # Group by category
    by_category = defaultdict(list)
    for qr in results:
        by_category[qr.category].append(qr)

    for category, queries in sorted(by_category.items()):
        print(f"\n{category.upper()} QUERIES ({len(queries)} total):")

        hybrid_wins = 0
        dense_wins = 0
        ties = 0

        for qr in queries:
            dense_score = sum([qr.dense_found_expected_fg, qr.dense_found_expected_participant, qr.dense_found_keywords])
            hybrid_score = sum([qr.hybrid_found_expected_fg, qr.hybrid_found_expected_participant, qr.hybrid_found_keywords])

            if hybrid_score > dense_score:
                hybrid_wins += 1
            elif dense_score > hybrid_score:
                dense_wins += 1
            else:
                ties += 1

        print(f"  Hybrid better: {hybrid_wins}")
        print(f"  Dense better:  {dense_wins}")
        print(f"  Tie:           {ties}")

    # Overall
    print("\nOVERALL:")
    total_hybrid = sum(1 for qr in results if (
        sum([qr.hybrid_found_expected_fg, qr.hybrid_found_expected_participant, qr.hybrid_found_keywords]) >
        sum([qr.dense_found_expected_fg, qr.dense_found_expected_participant, qr.dense_found_keywords])
    ))
    total_dense = sum(1 for qr in results if (
        sum([qr.dense_found_expected_fg, qr.dense_found_expected_participant, qr.dense_found_keywords]) >
        sum([qr.hybrid_found_expected_fg, qr.hybrid_found_expected_participant, qr.hybrid_found_keywords])
    ))
    total_tie = len(results) - total_hybrid - total_dense

    print(f"  Hybrid better: {total_hybrid}/{len(results)}")
    print(f"  Dense better:  {total_dense}/{len(results)}")
    print(f"  Tie:           {total_tie}/{len(results)}")

    # Latency
    avg_dense = sum(qr.dense_time_ms for qr in results) / len(results)
    avg_hybrid = sum(qr.hybrid_time_ms for qr in results) / len(results)
    print(f"\nAVG LATENCY:")
    print(f"  Dense:  {avg_dense:.0f}ms")
    print(f"  Hybrid: {avg_hybrid:.0f}ms (+{avg_hybrid - avg_dense:.0f}ms)")

    # Recommendation
    print("\n" + "-" * 70)
    if total_hybrid > total_dense and total_hybrid >= len(results) * 0.4:
        print("RECOMMENDATION: Hybrid shows improvement. Consider merging.")
    elif total_dense > total_hybrid:
        print("RECOMMENDATION: Dense is better. Do not merge hybrid.")
    else:
        print("RECOMMENDATION: Inconclusive. Consider tuning RRF parameters.")


def main():
    parser = argparse.ArgumentParser(description="Compare dense vs hybrid retrieval")
    parser.add_argument("--query", type=str, help="Run single query instead of test set")
    parser.add_argument("--no-router", action="store_true", help="Disable LLM router")
    parser.add_argument("--brief", action="store_true", help="Only show summary")
    args = parser.parse_args()

    if args.query:
        # Single query mode
        queries = [{
            "id": "adhoc",
            "query": args.query,
            "category": "adhoc",
        }]
    else:
        # Load test queries
        test_file = Path(__file__).parent / "hybrid_test_queries.json"
        with open(test_file) as f:
            data = json.load(f)
        queries = data["queries"]

    print(f"Running comparison on {len(queries)} queries...")
    print(f"Router: {'enabled' if not args.no_router else 'disabled'}")

    results = run_comparison(queries, use_router=not args.no_router, verbose=True)

    if not args.brief:
        print_detailed_results(results)

    print_summary(results)


if __name__ == "__main__":
    main()
