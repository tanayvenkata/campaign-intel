#!/usr/bin/env python3
"""
V2 Retrieval evaluation: LLM Router + Hierarchical + BGE embeddings.
Compares against V1 baseline.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import EVAL_DIR
from eval.metrics import (
    evaluate_positive_query,
    evaluate_negative_query,
    evaluate_synthetic_query,
    aggregate_metrics,
    RetrievalMetrics
)


def load_retriever_v2(use_router: bool = True, use_reranker: bool = False, verbose: bool = False):
    """Load V2 retriever."""
    from scripts.retrieve_v2 import FocusGroupRetrieverV2
    return FocusGroupRetrieverV2(use_router=use_router, use_reranker=use_reranker, verbose=verbose)


def load_test_queries(test_set: str = "retrieval") -> Dict:
    """Load test queries from JSON file.

    Args:
        test_set: "retrieval" (specific queries), "generation" (negative cases), or "combined" (all)
    """
    if test_set == "retrieval":
        query_file = EVAL_DIR / "test_queries_retrieval.json"
    elif test_set == "generation":
        query_file = EVAL_DIR / "test_queries_generation.json"
    else:
        query_file = EVAL_DIR / "test_queries_combined.json"

    if not query_file.exists():
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
    negative_threshold: float = 0.5,
    per_focus_group: bool = False,
    score_threshold: float = 0.75
) -> QueryResult:
    """Evaluate a single query."""
    query_id = query_data["id"]
    query_text = query_data["query"]
    category = query_data["category"]

    # Time the retrieval
    start_time = time.time()

    if per_focus_group:
        # Per-FG mode: query each focus group separately
        results_by_fg = retriever.retrieve_per_focus_group(
            query_text,
            top_k_per_fg=top_k,
            score_threshold=score_threshold
        )
        # Flatten results for evaluation
        # For per-FG mode, we get top-k per FG, so interleave results
        # to ensure recall calculation considers all FGs
        results = []
        fg_lists = list(results_by_fg.values())
        if fg_lists:
            max_len = max(len(lst) for lst in fg_lists)
            for i in range(max_len):
                for fg_results in fg_lists:
                    if i < len(fg_results):
                        results.append(fg_results[i])
    else:
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
        source_chunk_id = query_data.get("source_chunk_id", "")
        source_fg_id = query_data.get("source_focus_group", "")

        syn_result = evaluate_synthetic_query(
            retrieved_chunk_ids=retrieved_chunk_ids,
            source_chunk_id=source_chunk_id,
            k=top_k,
            retrieved_fg_ids=retrieved_fg_ids,
            source_fg_id=source_fg_id
        )
        passed = syn_result["hit"]
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
        # Positive case
        expected_fg_ids = query_data.get("expected_focus_groups", [])
        # For per-FG mode, evaluate with all results (not limited by top_k)
        # since we intentionally retrieve top-k per FG for diversity
        eval_k = len(retrieved_fg_ids) if per_focus_group else top_k
        pos_metrics = evaluate_positive_query(retrieved_fg_ids, expected_fg_ids, eval_k)

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
    use_router: bool = True,
    use_reranker: bool = False,
    per_focus_group: bool = False,
    score_threshold: float = 0.75,
    test_set: str = "retrieval",
    verbose: bool = True
) -> Dict[str, Any]:
    """Run full V2 retrieval evaluation."""
    if per_focus_group:
        version = "V3-PerFG"
    elif use_reranker:
        version = "V3"
    else:
        version = "V2"
    if verbose:
        print("=" * 60)
        print(f"{version} RETRIEVAL EVALUATION")
        print(f"Router: {'enabled' if use_router else 'disabled'}")
        print(f"Reranker: {'enabled' if use_reranker else 'disabled'}")
        print(f"Per-FG mode: {'enabled' if per_focus_group else 'disabled'}")
        if per_focus_group:
            print(f"Score threshold: {score_threshold}")
        print(f"Test set: {test_set}")
        print("=" * 60)

    # Load retriever
    if verbose:
        print(f"\nLoading {version} retriever...")
    retriever = load_retriever_v2(use_router=use_router, use_reranker=use_reranker, verbose=False)

    # Load queries
    if verbose:
        print("Loading test queries...")
    query_data = load_test_queries(test_set=test_set)
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
        result = evaluate_query(
            retriever, query, top_k, negative_threshold,
            per_focus_group=per_focus_group, score_threshold=score_threshold
        )
        results.append(result)

        cat = result.category
        if cat not in category_results:
            category_results[cat] = []
        category_results[cat].append(result)

        if verbose:
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{i+1}/{len(queries)}] {result.query_id}: {status} ({result.latency_ms:.0f}ms)")

    # Compute aggregate metrics
    positive_results = [r for r in results if r.category not in ["negative_case", "synthetic"]]
    negative_results = [r for r in results if r.category == "negative_case"]
    synthetic_results = [r for r in results if r.category == "synthetic"]

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

    total_passed = sum(1 for r in results if r.passed)
    total_queries = len(results)
    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0

    negative_passed = sum(1 for r in negative_results if r.passed)
    synthetic_passed = sum(1 for r in synthetic_results if r.passed)

    summary = {
        "version": "v3-perfg" if per_focus_group else ("v3" if use_reranker else "v2"),
        "router_enabled": use_router,
        "reranker_enabled": use_reranker,
        "per_focus_group": per_focus_group,
        "score_threshold": score_threshold if per_focus_group else None,
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

    for cat, cat_results in category_results.items():
        cat_passed = sum(1 for r in cat_results if r.passed)
        summary["by_category"][cat] = {
            "count": len(cat_results),
            "passed": cat_passed,
            "pass_rate": cat_passed / len(cat_results) if cat_results else 0
        }

    for r in results:
        if not r.passed:
            summary["failures"].append({
                "query_id": r.query_id,
                "query": r.query,
                "category": r.category,
                "details": r.details
            })

    return summary


def print_report(summary: Dict[str, Any], baseline: Dict[str, Any] = None):
    """Print formatted evaluation report with optional baseline comparison."""
    version = summary.get("version", "v2").upper()
    reranker_status = "ON" if summary.get('reranker_enabled', False) else "OFF"
    per_fg_status = "ON" if summary.get('per_focus_group', False) else "OFF"
    print("\n" + "=" * 60)
    print(f"{version} RETRIEVAL RESULTS")
    print(f"Router: {'ON' if summary['router_enabled'] else 'OFF'}, Reranker: {reranker_status}, Per-FG: {per_fg_status}")
    if summary.get('per_focus_group'):
        print(f"Score threshold: {summary.get('score_threshold', 0.75)}")
    print("=" * 60)

    overall = summary["overall"]
    pos = summary["positive_cases"]
    neg = summary["negative_cases"]
    syn = summary["synthetic_cases"]

    print(f"\nOVERALL: {overall['passed']}/{overall['total_queries']} passed ({overall['pass_rate']*100:.1f}%)")
    print(f"Average latency: {overall['avg_latency_ms']:.0f}ms")

    print("\nMETRICS:")
    recall_status = "PASS" if pos["avg_recall"] >= 0.7 else "FAIL"
    precision_status = "PASS" if pos["avg_precision"] >= 0.6 else "FAIL"
    mrr_status = "PASS" if pos["avg_mrr"] >= 0.5 else "FAIL"
    latency_status = "PASS" if overall["avg_latency_ms"] < 2000 else "FAIL"  # Higher threshold for router
    neg_status = "PASS" if neg["accuracy"] >= 0.8 else "FAIL"

    print(f"  Recall@5:     {pos['avg_recall']:.2f} (target: 0.70) [{recall_status}]")
    print(f"  Precision@5:  {pos['avg_precision']:.2f} (target: 0.60) [{precision_status}]")
    print(f"  MRR:          {pos['avg_mrr']:.2f} (target: 0.50) [{mrr_status}]")
    print(f"  Latency:      {overall['avg_latency_ms']:.0f}ms (target: 2000ms) [{latency_status}]")
    print(f"  Neg Accuracy: {neg['accuracy']:.2f} (target: 0.80) [{neg_status}]")
    print(f"  Synthetic:    {syn['hit_rate']:.2f} hit rate")

    # Comparison with baseline
    if baseline:
        print("\n" + "-" * 60)
        print("COMPARISON vs V1 BASELINE:")
        b_pos = baseline.get("positive_cases", {})
        b_overall = baseline.get("overall", {})

        recall_delta = pos["avg_recall"] - b_pos.get("avg_recall", 0)
        precision_delta = pos["avg_precision"] - b_pos.get("avg_precision", 0)
        mrr_delta = pos["avg_mrr"] - b_pos.get("avg_mrr", 0)

        print(f"  Recall:    {pos['avg_recall']:.2f} vs {b_pos.get('avg_recall', 0):.2f} ({'+' if recall_delta >= 0 else ''}{recall_delta:.2f})")
        print(f"  Precision: {pos['avg_precision']:.2f} vs {b_pos.get('avg_precision', 0):.2f} ({'+' if precision_delta >= 0 else ''}{precision_delta:.2f})")
        print(f"  MRR:       {pos['avg_mrr']:.2f} vs {b_pos.get('avg_mrr', 0):.2f} ({'+' if mrr_delta >= 0 else ''}{mrr_delta:.2f})")

    # By category
    print("\nBY CATEGORY:")
    for cat, stats in summary["by_category"].items():
        print(f"  {cat}: {stats['passed']}/{stats['count']} ({stats['pass_rate']*100:.0f}%)")

    # Failures
    if summary["failures"]:
        print(f"\nFAILURES ({len(summary['failures'])}):")
        for f in summary["failures"][:10]:
            print(f"  - {f['query_id']}: {f['query'][:50]}...")
            if "missed" in f["details"]:
                print(f"    Missed: {f['details']['missed']}")

    print("\n" + "=" * 60)


def main():
    """Run V2 evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description="Run V2 retrieval evaluation")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    parser.add_argument("--threshold", type=float, default=0.5, help="Negative case threshold")
    parser.add_argument("--category", type=str, nargs="+", help="Categories to evaluate")
    parser.add_argument("--no-router", action="store_true", help="Disable LLM router")
    parser.add_argument("--reranker", action="store_true", help="Enable cross-encoder reranking (V3)")
    parser.add_argument("--per-fg", action="store_true",
                        help="Use per-focus-group retrieval for diversity")
    parser.add_argument("--score-threshold", type=float, default=0.75,
                        help="Score threshold for per-FG mode (default: 0.75)")
    parser.add_argument("--test-set", type=str, default="retrieval",
                        choices=["retrieval", "generation", "combined"],
                        help="Test set to use (default: retrieval)")
    parser.add_argument("--compare-v1", action="store_true", help="Compare with V1 baseline")
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress")

    args = parser.parse_args()

    # Run V2/V3 evaluation
    summary = run_evaluation(
        top_k=args.top_k,
        negative_threshold=args.threshold,
        categories=args.category,
        use_router=not args.no_router,
        use_reranker=args.reranker,
        per_focus_group=args.per_fg,
        score_threshold=args.score_threshold,
        test_set=args.test_set,
        verbose=not args.quiet
    )

    # Optionally run V1 for comparison
    baseline = None
    if args.compare_v1:
        print("\n" + "=" * 60)
        print("Running V1 baseline for comparison...")
        print("=" * 60)
        from eval.run_retrieval_eval import run_evaluation as run_v1_eval
        baseline = run_v1_eval(
            top_k=args.top_k,
            negative_threshold=args.threshold,
            categories=args.category,
            verbose=not args.quiet
        )

    # Print report
    print_report(summary, baseline)

    # Save to file
    if args.output:
        output_path = Path(args.output)
        output_data = {"v2": summary}
        if baseline:
            output_data["v1"] = baseline
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
