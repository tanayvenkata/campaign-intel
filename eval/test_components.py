#!/usr/bin/env python3
"""
Unified component testing with latency and delta tracking.
Tests each V3 component in isolation against V2 baseline.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import EVAL_DIR
from eval.run_retrieval_eval_v2 import (
    load_test_queries,
    evaluate_query,
    load_retriever_v2
)


@dataclass
class ComponentTestResult:
    """Result of testing a single component."""
    component: str
    baseline_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    baseline_latency_ms: float
    test_latency_ms: float
    delta_recall: float
    delta_precision: float
    delta_mrr: float
    delta_latency_ms: float
    worth_it: bool
    semantic_queries_passed: List[str]
    semantic_queries_failed: List[str]
    details: Dict[str, Any]


# V2 Baseline metrics (from previous eval)
V2_BASELINE = {
    "passed": 14,
    "total": 22,
    "recall": 0.78,
    "precision": 0.75,
    "mrr": 0.74,
    "latency_ms": 717,
    "ohio_focused_pass_rate": 0.90,
    "semantic_pass_rate": 0.50
}

# Semantic test queries (the ones that fail with V2)
SEMANTIC_QUERIES = ["rachel-002", "ohio-004"]


def run_baseline_eval(retriever, queries: List[Dict], verbose: bool = True) -> Dict:
    """Run baseline V2 evaluation."""
    results = []
    total_latency = 0

    for query in queries:
        start = time.time()
        result = evaluate_query(retriever, query)
        latency = (time.time() - start) * 1000
        total_latency += latency
        results.append(result)

    passed = sum(1 for r in results if r.passed)
    positive_results = [r for r in results if r.category not in ["negative_case", "synthetic"]]

    avg_recall = sum(r.metrics.get("recall", 0) for r in positive_results) / len(positive_results) if positive_results else 0
    avg_precision = sum(r.metrics.get("precision", 0) for r in positive_results) / len(positive_results) if positive_results else 0
    avg_mrr = sum(r.metrics.get("mrr", 0) for r in positive_results) / len(positive_results) if positive_results else 0

    semantic_passed = [r.query_id for r in results if r.query_id in SEMANTIC_QUERIES and r.passed]

    return {
        "passed": passed,
        "total": len(results),
        "recall": avg_recall,
        "precision": avg_precision,
        "mrr": avg_mrr,
        "latency_ms": total_latency / len(results),
        "semantic_passed": semantic_passed,
        "results": results
    }


def test_query_enhancement(verbose: bool = True) -> ComponentTestResult:
    """Test query enhancement in isolation."""
    from scripts.query_enhance import QueryEnhancer
    from scripts.retrieve import FocusGroupRetrieverV2

    if verbose:
        print("\n" + "=" * 60)
        print("TESTING: Query Enhancement")
        print("=" * 60)

    # Load components
    enhancer = QueryEnhancer(verbose=False)
    retriever = FocusGroupRetrieverV2(use_router=True, verbose=False)

    # Load queries
    query_data = load_test_queries("retrieval")
    queries = query_data["queries"]

    # Run with enhancement
    results = []
    total_latency = 0

    for i, query in enumerate(queries):
        # Enhance query
        start = time.time()
        enhanced_query = enhancer.expand(query["query"])
        enhance_time = (time.time() - start) * 1000

        # Create modified query dict
        enhanced_query_data = query.copy()
        enhanced_query_data["query"] = enhanced_query

        # Run retrieval
        start = time.time()
        result = evaluate_query(retriever, enhanced_query_data)
        retrieval_time = (time.time() - start) * 1000

        total_latency += enhance_time + retrieval_time
        results.append(result)

        if verbose:
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{i+1}/{len(queries)}] {result.query_id}: {status} ({enhance_time + retrieval_time:.0f}ms)")

    # Calculate metrics
    passed = sum(1 for r in results if r.passed)
    positive_results = [r for r in results if r.category not in ["negative_case", "synthetic"]]

    avg_recall = sum(r.metrics.get("recall", 0) for r in positive_results) / len(positive_results) if positive_results else 0
    avg_precision = sum(r.metrics.get("precision", 0) for r in positive_results) / len(positive_results) if positive_results else 0
    avg_mrr = sum(r.metrics.get("mrr", 0) for r in positive_results) / len(positive_results) if positive_results else 0
    avg_latency = total_latency / len(results)

    semantic_passed = [r.query_id for r in results if r.query_id in SEMANTIC_QUERIES and r.passed]
    semantic_failed = [r.query_id for r in results if r.query_id in SEMANTIC_QUERIES and not r.passed]

    # Calculate deltas
    delta_recall = avg_recall - V2_BASELINE["recall"]
    delta_precision = avg_precision - V2_BASELINE["precision"]
    delta_mrr = avg_mrr - V2_BASELINE["mrr"]
    delta_latency = avg_latency - V2_BASELINE["latency_ms"]

    # Worth it? +5% recall/precision AND <500ms latency increase
    worth_it = (delta_recall > 0.05 or delta_precision > 0.05) and delta_latency < 500

    return ComponentTestResult(
        component="query_enhancement",
        baseline_metrics={
            "recall": V2_BASELINE["recall"],
            "precision": V2_BASELINE["precision"],
            "mrr": V2_BASELINE["mrr"],
            "passed": V2_BASELINE["passed"]
        },
        test_metrics={
            "recall": avg_recall,
            "precision": avg_precision,
            "mrr": avg_mrr,
            "passed": passed
        },
        baseline_latency_ms=V2_BASELINE["latency_ms"],
        test_latency_ms=avg_latency,
        delta_recall=delta_recall,
        delta_precision=delta_precision,
        delta_mrr=delta_mrr,
        delta_latency_ms=delta_latency,
        worth_it=worth_it,
        semantic_queries_passed=semantic_passed,
        semantic_queries_failed=semantic_failed,
        details={
            "total_queries": len(queries),
            "passed": passed,
            "failed": len(queries) - passed
        }
    )


def test_reranking(model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2", verbose: bool = True) -> ComponentTestResult:
    """Test reranking in isolation."""
    from scripts.rerank import Reranker
    from scripts.retrieve import FocusGroupRetrieverV2

    if verbose:
        print("\n" + "=" * 60)
        print(f"TESTING: Reranking ({model_name})")
        print("=" * 60)

    # Load components
    reranker = Reranker(model_name=model_name)
    retriever = FocusGroupRetrieverV2(use_router=True, verbose=False)

    # Load queries
    query_data = load_test_queries("retrieval")
    queries = query_data["queries"]

    results = []
    total_latency = 0

    for i, query in enumerate(queries):
        start = time.time()

        # Get candidates (top 20)
        candidates = retriever.retrieve(query["query"], top_k=20)

        # Rerank
        reranked = reranker.rerank(query["query"], candidates, top_k=5)

        latency = (time.time() - start) * 1000
        total_latency += latency

        # Evaluate reranked results
        retrieved_fg_ids = [r.focus_group_id for r in reranked]
        expected_fg_ids = query.get("expected_focus_groups", [])

        if expected_fg_ids:
            found = set(retrieved_fg_ids) & set(expected_fg_ids)
            passed = len(found) > 0
            recall = len(found) / len(expected_fg_ids) if expected_fg_ids else 0
        else:
            passed = True
            recall = 1.0

        results.append({
            "query_id": query["id"],
            "category": query["category"],
            "passed": passed,
            "recall": recall,
            "latency_ms": latency
        })

        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"  [{i+1}/{len(queries)}] {query['id']}: {status} ({latency:.0f}ms)")

    # Calculate metrics
    passed = sum(1 for r in results if r["passed"])
    positive_results = [r for r in results if r["category"] not in ["negative_case", "synthetic"]]

    avg_recall = sum(r["recall"] for r in positive_results) / len(positive_results) if positive_results else 0
    avg_latency = total_latency / len(results)

    semantic_passed = [r["query_id"] for r in results if r["query_id"] in SEMANTIC_QUERIES and r["passed"]]
    semantic_failed = [r["query_id"] for r in results if r["query_id"] in SEMANTIC_QUERIES and not r["passed"]]

    delta_recall = avg_recall - V2_BASELINE["recall"]
    delta_latency = avg_latency - V2_BASELINE["latency_ms"]

    worth_it = delta_recall > 0.05 and delta_latency < 500

    return ComponentTestResult(
        component=f"reranking_{model_name.split('/')[-1]}",
        baseline_metrics={"recall": V2_BASELINE["recall"], "passed": V2_BASELINE["passed"]},
        test_metrics={"recall": avg_recall, "passed": passed},
        baseline_latency_ms=V2_BASELINE["latency_ms"],
        test_latency_ms=avg_latency,
        delta_recall=delta_recall,
        delta_precision=0,  # Need more detailed eval for precision
        delta_mrr=0,
        delta_latency_ms=delta_latency,
        worth_it=worth_it,
        semantic_queries_passed=semantic_passed,
        semantic_queries_failed=semantic_failed,
        details={"model": model_name, "passed": passed, "total": len(queries)}
    )


def test_hyde(verbose: bool = True) -> ComponentTestResult:
    """Test HyDE in isolation."""
    from scripts.hyde import HyDE
    from scripts.retrieve import FocusGroupRetrieverV2

    if verbose:
        print("\n" + "=" * 60)
        print("TESTING: HyDE (Hypothetical Document Embeddings)")
        print("=" * 60)

    hyde = HyDE(verbose=False)
    retriever = FocusGroupRetrieverV2(use_router=True, verbose=False)

    query_data = load_test_queries("retrieval")
    queries = query_data["queries"]

    results = []
    total_latency = 0

    for i, query in enumerate(queries):
        start = time.time()

        # Generate hypothetical and search
        hyde_results = hyde.search(query["query"], retriever, top_k=5)

        latency = (time.time() - start) * 1000
        total_latency += latency

        # Evaluate
        retrieved_fg_ids = [r.focus_group_id for r in hyde_results]
        expected_fg_ids = query.get("expected_focus_groups", [])

        if expected_fg_ids:
            found = set(retrieved_fg_ids) & set(expected_fg_ids)
            passed = len(found) > 0
            recall = len(found) / len(expected_fg_ids) if expected_fg_ids else 0
        else:
            passed = True
            recall = 1.0

        results.append({
            "query_id": query["id"],
            "category": query["category"],
            "passed": passed,
            "recall": recall,
            "latency_ms": latency
        })

        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"  [{i+1}/{len(queries)}] {query['id']}: {status} ({latency:.0f}ms)")

    passed = sum(1 for r in results if r["passed"])
    positive_results = [r for r in results if r["category"] not in ["negative_case", "synthetic"]]
    avg_recall = sum(r["recall"] for r in positive_results) / len(positive_results) if positive_results else 0
    avg_latency = total_latency / len(results)

    semantic_passed = [r["query_id"] for r in results if r["query_id"] in SEMANTIC_QUERIES and r["passed"]]
    semantic_failed = [r["query_id"] for r in results if r["query_id"] in SEMANTIC_QUERIES and not r["passed"]]

    delta_recall = avg_recall - V2_BASELINE["recall"]
    delta_latency = avg_latency - V2_BASELINE["latency_ms"]

    worth_it = delta_recall > 0.05 and delta_latency < 500

    return ComponentTestResult(
        component="hyde",
        baseline_metrics={"recall": V2_BASELINE["recall"], "passed": V2_BASELINE["passed"]},
        test_metrics={"recall": avg_recall, "passed": passed},
        baseline_latency_ms=V2_BASELINE["latency_ms"],
        test_latency_ms=avg_latency,
        delta_recall=delta_recall,
        delta_precision=0,
        delta_mrr=0,
        delta_latency_ms=delta_latency,
        worth_it=worth_it,
        semantic_queries_passed=semantic_passed,
        semantic_queries_failed=semantic_failed,
        details={"passed": passed, "total": len(queries)}
    )


def test_doc2query(verbose: bool = True) -> ComponentTestResult:
    """Test Doc2Query in isolation."""
    from scripts.retrieve_doc2query import Doc2QueryRetriever

    if verbose:
        print("\n" + "=" * 60)
        print("TESTING: Doc2Query (Document Expansion)")
        print("=" * 60)

    retriever = Doc2QueryRetriever(use_router=True, use_reranker=False, verbose=False)

    query_data = load_test_queries("retrieval")
    queries = query_data["queries"]

    results = []
    total_latency = 0

    for i, query in enumerate(queries):
        start = time.time()

        doc2query_results = retriever.retrieve(query["query"], top_k=5)

        latency = (time.time() - start) * 1000
        total_latency += latency

        # Evaluate
        retrieved_fg_ids = [r.focus_group_id for r in doc2query_results]
        expected_fg_ids = query.get("expected_focus_groups", [])

        if expected_fg_ids:
            found = set(retrieved_fg_ids) & set(expected_fg_ids)
            passed = len(found) > 0
            recall = len(found) / len(expected_fg_ids) if expected_fg_ids else 0
        else:
            passed = True
            recall = 1.0

        results.append({
            "query_id": query["id"],
            "category": query["category"],
            "passed": passed,
            "recall": recall,
            "latency_ms": latency
        })

        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"  [{i+1}/{len(queries)}] {query['id']}: {status} ({latency:.0f}ms)")

    passed = sum(1 for r in results if r["passed"])
    positive_results = [r for r in results if r["category"] not in ["negative_case", "synthetic"]]
    avg_recall = sum(r["recall"] for r in positive_results) / len(positive_results) if positive_results else 0
    avg_latency = total_latency / len(results)

    semantic_passed = [r["query_id"] for r in results if r["query_id"] in SEMANTIC_QUERIES and r["passed"]]
    semantic_failed = [r["query_id"] for r in results if r["query_id"] in SEMANTIC_QUERIES and not r["passed"]]

    delta_recall = avg_recall - V2_BASELINE["recall"]
    delta_latency = avg_latency - V2_BASELINE["latency_ms"]

    worth_it = delta_recall > 0.05 and delta_latency < 500

    return ComponentTestResult(
        component="doc2query",
        baseline_metrics={"recall": V2_BASELINE["recall"], "passed": V2_BASELINE["passed"]},
        test_metrics={"recall": avg_recall, "passed": passed},
        baseline_latency_ms=V2_BASELINE["latency_ms"],
        test_latency_ms=avg_latency,
        delta_recall=delta_recall,
        delta_precision=0,
        delta_mrr=0,
        delta_latency_ms=delta_latency,
        worth_it=worth_it,
        semantic_queries_passed=semantic_passed,
        semantic_queries_failed=semantic_failed,
        details={"passed": passed, "total": len(queries)}
    )


def print_component_result(result: ComponentTestResult):
    """Print formatted component test result."""
    print("\n" + "=" * 60)
    print(f"{result.component.upper()} TEST RESULTS")
    print("=" * 60)

    print(f"\nBaseline (V2):  {result.baseline_metrics['passed']}/22 passed, "
          f"Recall={result.baseline_metrics['recall']:.2f}, "
          f"Latency={result.baseline_latency_ms:.0f}ms")

    print(f"With Component: {result.test_metrics['passed']}/22 passed, "
          f"Recall={result.test_metrics['recall']:.2f}, "
          f"Latency={result.test_latency_ms:.0f}ms")

    print(f"\nDelta:")
    print(f"  Recall:    {result.delta_recall:+.2f}")
    print(f"  Precision: {result.delta_precision:+.2f}")
    print(f"  MRR:       {result.delta_mrr:+.2f}")
    print(f"  Latency:   {result.delta_latency_ms:+.0f}ms")

    print(f"\nSemantic Queries:")
    print(f"  Passed: {result.semantic_queries_passed}")
    print(f"  Failed: {result.semantic_queries_failed}")

    worth_status = "YES" if result.worth_it else "NO"
    print(f"\nWorth it: {worth_status}")
    print("  (Threshold: +5% recall/precision, <500ms latency)")

    print("=" * 60)


def main():
    """Run component tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Test V3 components")
    parser.add_argument("--component", choices=["enhancement", "hyde", "rerank", "doc2query", "all"],
                        default="enhancement", help="Component to test")
    parser.add_argument("--rerank-model", default="cross-encoder/ms-marco-MiniLM-L6-v2",
                        help="Reranker model to test")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()

    results = []

    if args.component in ["enhancement", "all"]:
        result = test_query_enhancement(verbose=not args.quiet)
        print_component_result(result)
        results.append(asdict(result))

    if args.component in ["hyde", "all"]:
        result = test_hyde(verbose=not args.quiet)
        print_component_result(result)
        results.append(asdict(result))

    if args.component in ["rerank", "all"]:
        result = test_reranking(model_name=args.rerank_model, verbose=not args.quiet)
        print_component_result(result)
        results.append(asdict(result))

    if args.component in ["doc2query", "all"]:
        result = test_doc2query(verbose=not args.quiet)
        print_component_result(result)
        results.append(asdict(result))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
