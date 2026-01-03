#!/usr/bin/env python3
"""
Retrieval-only evaluation for focus group search.
Tests retrieval quality before adding generation.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import EVAL_DIR
from eval.metrics import (
    evaluate_positive_query,
    evaluate_negative_query,
    evaluate_synthetic_query,
    aggregate_metrics,
    RetrievalMetrics
)

# Lazy import for retriever
FocusGroupRetriever = None


def load_retriever():
    """Load retriever with lazy import."""
    global FocusGroupRetriever
    from scripts.retrieve import FocusGroupRetriever as _FocusGroupRetriever
    FocusGroupRetriever = _FocusGroupRetriever
    return FocusGroupRetriever()


def load_test_queries(use_combined: bool = True) -> Dict:
    """Load test queries from JSON file."""
    if use_combined:
        query_file = EVAL_DIR / "test_queries_combined.json"
        if not query_file.exists():
            query_file = EVAL_DIR / "test_queries.json"
    else:
        query_file = EVAL_DIR / "test_queries.json"

    with open(query_file) as f:
        return json.load(f)


@dataclass
class QueryResult:
    """Result for a single query evaluation."""
    query_id: str
    query: str
    category: str
    passed: bool
    metrics: Dict[str, Any]
    latency_ms: float
    details: Dict[str, Any]


def evaluate_query(
    retriever,
    query_data: Dict,
    top_k: int = 5,
    negative_threshold: float = 0.5
) -> QueryResult:
    """
    Evaluate a single query.

    Args:
        retriever: FocusGroupRetriever instance
        query_data: Query dict from test_queries.json
        top_k: Number of results to retrieve
        negative_threshold: Score threshold for negative cases

    Returns:
        QueryResult with evaluation details
    """
    query_id = query_data["id"]
    query_text = query_data["query"]
    category = query_data["category"]

    # Time the retrieval
    start_time = time.time()
    results = retriever.retrieve(query_text, top_k=top_k)
    latency_ms = (time.time() - start_time) * 1000

    # Extract data from results
    retrieved_fg_ids = [r.focus_group_id for r in results]
    retrieved_chunk_ids = [r.chunk_id for r in results]
    retrieved_chunks = [
        {"chunk_id": r.chunk_id, "score": r.score, "focus_group_id": r.focus_group_id}
        for r in results
    ]

    # Evaluate based on category
    if category == "negative_case":
        # Negative case evaluation
        neg_result = evaluate_negative_query(retrieved_chunks, negative_threshold)
        passed = neg_result["passed"]
        metrics = {"max_score": neg_result["max_score"]}
        details = {
            "expected_result": query_data.get("expected_result", "no_relevant_data"),
            "all_scores_low": neg_result["all_scores_low"],
            "scores": neg_result.get("scores", []),
            "retrieved_fg_ids": retrieved_fg_ids
        }

    elif category == "synthetic":
        # Synthetic query - check if source FOCUS GROUP is retrieved (not exact chunk)
        source_chunk_id = query_data.get("source_chunk_id", "")
        source_fg_id = query_data.get("source_focus_group", "")

        syn_result = evaluate_synthetic_query(
            retrieved_chunk_ids=retrieved_chunk_ids,
            source_chunk_id=source_chunk_id,
            k=top_k,
            retrieved_fg_ids=retrieved_fg_ids,
            source_fg_id=source_fg_id
        )
        passed = syn_result["hit"]  # Now based on focus group match
        metrics = {
            "mrr": syn_result["mrr"],
            "rank": syn_result["rank"],
            "exact_chunk_hit": syn_result.get("exact_chunk_hit", False)
        }
        details = {
            "source_chunk_id": source_chunk_id,
            "source_fg_id": source_fg_id,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_fg_ids": retrieved_fg_ids,
            "hit": syn_result["hit"],
            "exact_chunk_hit": syn_result.get("exact_chunk_hit", False)
        }

    else:
        # Positive case (rachel_test, ohio_2024_focused)
        expected_fg_ids = query_data.get("expected_focus_groups", [])
        pos_metrics = evaluate_positive_query(retrieved_fg_ids, expected_fg_ids, top_k)

        # Query passes if recall > 0.5 (found at least half of expected)
        passed = pos_metrics.recall_at_k >= 0.5
        metrics = {
            "recall": pos_metrics.recall_at_k,
            "precision": pos_metrics.precision_at_k,
            "mrr": pos_metrics.mrr,
            "hit": pos_metrics.hit
        }
        details = {
            "expected_fg_ids": expected_fg_ids,
            "retrieved_fg_ids": retrieved_fg_ids,
            "found": list(set(retrieved_fg_ids) & set(expected_fg_ids)),
            "missed": list(set(expected_fg_ids) - set(retrieved_fg_ids))
        }

    return QueryResult(
        query_id=query_id,
        query=query_text,
        category=category,
        passed=passed,
        metrics=metrics,
        latency_ms=latency_ms,
        details=details
    )


def run_evaluation(
    top_k: int = 5,
    negative_threshold: float = 0.5,
    categories: List[str] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run full retrieval evaluation.

    Args:
        top_k: Number of results to retrieve
        negative_threshold: Score threshold for negative cases
        categories: List of categories to evaluate (None = all)
        verbose: Print progress

    Returns:
        Dict with evaluation results
    """
    if verbose:
        print("=" * 60)
        print("RETRIEVAL EVALUATION")
        print("=" * 60)

    # Load retriever
    if verbose:
        print("\nLoading retriever...")
    retriever = load_retriever()

    # Load queries
    if verbose:
        print("Loading test queries...")
    query_data = load_test_queries()
    queries = query_data["queries"]

    # Filter by category if specified
    if categories:
        queries = [q for q in queries if q["category"] in categories]

    if verbose:
        print(f"Evaluating {len(queries)} queries...\n")

    # Run evaluation
    results: List[QueryResult] = []
    category_results: Dict[str, List[QueryResult]] = {}

    for i, query in enumerate(queries):
        result = evaluate_query(retriever, query, top_k, negative_threshold)
        results.append(result)

        # Group by category
        cat = result.category
        if cat not in category_results:
            category_results[cat] = []
        category_results[cat].append(result)

        # Progress indicator
        if verbose:
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{i+1}/{len(queries)}] {result.query_id}: {status} ({result.latency_ms:.0f}ms)")

    # Compute aggregate metrics
    positive_results = [r for r in results if r.category not in ["negative_case", "synthetic"]]
    negative_results = [r for r in results if r.category == "negative_case"]
    synthetic_results = [r for r in results if r.category == "synthetic"]

    # Aggregate positive metrics
    positive_metrics = []
    for r in positive_results:
        if "recall" in r.metrics:
            positive_metrics.append(RetrievalMetrics(
                recall_at_k=r.metrics["recall"],
                precision_at_k=r.metrics["precision"],
                mrr=r.metrics["mrr"],
                hit=r.metrics.get("hit", False)
            ))

    aggregated = aggregate_metrics(positive_metrics)

    # Compute overall stats
    total_passed = sum(1 for r in results if r.passed)
    total_queries = len(results)
    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0

    negative_passed = sum(1 for r in negative_results if r.passed)
    synthetic_passed = sum(1 for r in synthetic_results if r.passed)

    # Build summary
    summary = {
        "overall": {
            "total_queries": total_queries,
            "passed": total_passed,
            "failed": total_queries - total_passed,
            "pass_rate": total_passed / total_queries if total_queries else 0,
            "avg_latency_ms": avg_latency
        },
        "positive_cases": {
            "count": len(positive_results),
            "avg_recall": aggregated["avg_recall"],
            "avg_precision": aggregated["avg_precision"],
            "avg_mrr": aggregated["avg_mrr"],
            "hit_rate": aggregated["hit_rate"]
        },
        "negative_cases": {
            "count": len(negative_results),
            "passed": negative_passed,
            "accuracy": negative_passed / len(negative_results) if negative_results else 1.0
        },
        "synthetic_cases": {
            "count": len(synthetic_results),
            "passed": synthetic_passed,
            "hit_rate": synthetic_passed / len(synthetic_results) if synthetic_results else 1.0
        },
        "by_category": {},
        "failures": [],
        "all_results": [asdict(r) for r in results]
    }

    # Category breakdown
    for cat, cat_results in category_results.items():
        cat_passed = sum(1 for r in cat_results if r.passed)
        summary["by_category"][cat] = {
            "count": len(cat_results),
            "passed": cat_passed,
            "pass_rate": cat_passed / len(cat_results) if cat_results else 0
        }

    # Record failures
    for r in results:
        if not r.passed:
            summary["failures"].append({
                "query_id": r.query_id,
                "query": r.query,
                "category": r.category,
                "details": r.details
            })

    return summary


def print_report(summary: Dict[str, Any]):
    """Print formatted evaluation report."""
    print("\n" + "=" * 60)
    print("RETRIEVAL EVALUATION RESULTS")
    print("=" * 60)

    # Overall metrics
    overall = summary["overall"]
    print(f"\nOVERALL: {overall['passed']}/{overall['total_queries']} passed ({overall['pass_rate']*100:.1f}%)")
    print(f"Average latency: {overall['avg_latency_ms']:.0f}ms")

    # Targets
    pos = summary["positive_cases"]
    neg = summary["negative_cases"]

    print("\nMETRICS vs TARGETS:")
    recall_status = "PASS" if pos["avg_recall"] >= 0.7 else "FAIL"
    precision_status = "PASS" if pos["avg_precision"] >= 0.6 else "FAIL"
    mrr_status = "PASS" if pos["avg_mrr"] >= 0.5 else "FAIL"
    latency_status = "PASS" if overall["avg_latency_ms"] < 500 else "FAIL"
    neg_status = "PASS" if neg["accuracy"] >= 0.8 else "FAIL"

    print(f"  Recall@5:     {pos['avg_recall']:.2f} (target: 0.70) [{recall_status}]")
    print(f"  Precision@5:  {pos['avg_precision']:.2f} (target: 0.60) [{precision_status}]")
    print(f"  MRR:          {pos['avg_mrr']:.2f} (target: 0.50) [{mrr_status}]")
    print(f"  Latency:      {overall['avg_latency_ms']:.0f}ms (target: 500ms) [{latency_status}]")
    print(f"  Neg Accuracy: {neg['accuracy']:.2f} (target: 0.80) [{neg_status}]")

    # By category
    print("\nBY CATEGORY:")
    for cat, stats in summary["by_category"].items():
        print(f"  {cat}: {stats['passed']}/{stats['count']} ({stats['pass_rate']*100:.0f}%)")

    # Failures
    if summary["failures"]:
        print(f"\nFAILURES ({len(summary['failures'])}):")
        for f in summary["failures"][:10]:  # Show first 10
            print(f"  - {f['query_id']}: {f['query'][:50]}...")
            if "missed" in f["details"]:
                print(f"    Missed: {f['details']['missed']}")
            if "max_score" in f["details"]:
                print(f"    Max score: {f['details'].get('max_score', 'N/A')}")

    # Overall pass/fail
    print("\n" + "=" * 60)
    all_pass = (
        pos["avg_recall"] >= 0.7 and
        pos["avg_precision"] >= 0.6 and
        pos["avg_mrr"] >= 0.5 and
        overall["avg_latency_ms"] < 500 and
        neg["accuracy"] >= 0.8
    )
    if all_pass:
        print("RESULT: ALL TARGETS MET - Ready for generation pipeline")
    else:
        print("RESULT: TARGETS NOT MET - Retrieval needs improvement")
    print("=" * 60)


def main():
    """Run evaluation and print report."""
    import argparse

    parser = argparse.ArgumentParser(description="Run retrieval evaluation")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to retrieve")
    parser.add_argument("--threshold", type=float, default=0.5, help="Negative case score threshold")
    parser.add_argument("--category", type=str, nargs="+", help="Categories to evaluate")
    parser.add_argument("--output", type=str, help="Output JSON file for results")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    # Run evaluation
    summary = run_evaluation(
        top_k=args.top_k,
        negative_threshold=args.threshold,
        categories=args.category,
        verbose=not args.quiet
    )

    # Print report
    print_report(summary)

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
