#!/usr/bin/env python3
"""
DeepEval retrieval evaluation with LLM-as-judge.
Uses GPT-4o-mini via DeepEval's native OpenAI support.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import EVAL_DIR, OPENAI_API_KEY
import openai

# DeepEval imports
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    ContextualRelevancyMetric,
    ContextualRecallMetric,
    ContextualPrecisionMetric
)
from deepeval.evaluate import DisplayConfig, AsyncConfig, ErrorConfig

# Model to use for evaluation
EVAL_MODEL = "gpt-4o-mini"

# OpenAI client for generating expected answers
_openai_client = None

def get_openai_client():
    """Get or create OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client

# Lazy import for retriever
FocusGroupRetriever = None


def load_retriever():
    """Load retriever with lazy import."""
    global FocusGroupRetriever
    from scripts.retrieve import FocusGroupRetriever as _FocusGroupRetriever
    FocusGroupRetriever = _FocusGroupRetriever
    return FocusGroupRetriever()


def load_test_queries() -> List[Dict]:
    """Load positive test queries (rachel_test + ohio_2024_focused)."""
    query_file = EVAL_DIR / "test_queries.json"

    with open(query_file) as f:
        data = json.load(f)

    # Filter to positive cases only (skip negative and synthetic)
    positive_categories = ["rachel_test", "ohio_2024_focused"]
    queries = [q for q in data["queries"] if q["category"] in positive_categories]

    return queries


def generate_expected_answer(query: str, chunks: List[str]) -> str:
    """
    Generate expected answer using OpenAI.

    Args:
        query: The query
        chunks: Retrieved chunk contents

    Returns:
        Expected answer string
    """
    chunks_text = "\n\n".join([f"Quote {i+1}: \"{c}\"" for i, c in enumerate(chunks[:5])])

    prompt = f"""Given this query about political focus groups:
"{query}"

And these relevant quotes from focus group transcripts:
{chunks_text}

Write a brief (2-3 sentence) expected answer that captures the key themes a good retrieval system should find. Focus on the main voter sentiments expressed in these quotes.

Expected answer:"""

    client = get_openai_client()
    response = client.chat.completions.create(
        model=EVAL_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256
    )
    return response.choices[0].message.content


def create_test_cases(
    queries: List[Dict],
    retriever,
    top_k: int = 5
) -> List[LLMTestCase]:
    """
    Create DeepEval test cases from queries.

    Args:
        queries: List of query dicts
        retriever: FocusGroupRetriever instance
        top_k: Number of chunks to retrieve

    Returns:
        List of LLMTestCase objects
    """
    test_cases = []

    for i, query_data in enumerate(queries):
        query_id = query_data["id"]
        query_text = query_data["query"]

        print(f"  [{i+1}/{len(queries)}] Processing {query_id}...")

        # Run retrieval
        results = retriever.retrieve(query_text, top_k=top_k)
        retrieval_context = [r.content for r in results]

        # Generate expected answer if not provided
        expected_output = query_data.get("expected_output")
        if not expected_output:
            print(f"    Generating expected answer...")
            expected_output = generate_expected_answer(query_text, retrieval_context)

        # Create test case
        test_case = LLMTestCase(
            input=query_text,
            actual_output="",  # Not using actual output for retrieval-only eval
            retrieval_context=retrieval_context,
            expected_output=expected_output
        )
        test_case.additional_metadata = {"query_id": query_id}
        test_cases.append(test_case)

    return test_cases


def run_deepeval_evaluation(
    top_k: int = 5,
    threshold: float = 0.7,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run DeepEval retrieval evaluation.

    Args:
        top_k: Number of chunks to retrieve
        threshold: Passing threshold for metrics
        verbose: Print progress

    Returns:
        Dict with evaluation results
    """
    if verbose:
        print("=" * 60)
        print("DEEPEVAL RETRIEVAL EVALUATION")
        print("=" * 60)

    # Load components
    if verbose:
        print("\nLoading components...")

    retriever = load_retriever()

    if verbose:
        print(f"  Model: {EVAL_MODEL}")

    # Load queries
    if verbose:
        print("\nLoading test queries...")
    queries = load_test_queries()
    if verbose:
        print(f"  Found {len(queries)} queries")

    # Create test cases
    if verbose:
        print("\nCreating test cases (retrieval + expected answer generation)...")
    test_cases = create_test_cases(queries, retriever, top_k)

    # Create metrics - use native OpenAI support
    if verbose:
        print("\nInitializing metrics...")
    metrics = [
        ContextualRelevancyMetric(model=EVAL_MODEL, threshold=threshold),
        ContextualRecallMetric(model=EVAL_MODEL, threshold=threshold),
        ContextualPrecisionMetric(model=EVAL_MODEL, threshold=threshold)
    ]

    # Run evaluation
    if verbose:
        print("\nRunning evaluation (this may take a minute)...")

    results = evaluate(
        test_cases=test_cases,
        metrics=metrics,
        display_config=DisplayConfig(print_results=False, show_indicator=False),
        error_config=ErrorConfig(ignore_errors=True)  # Continue past intermittent LLM JSON errors
    )

    # Process results
    summary = process_results(results, test_cases, queries, threshold, verbose)

    return summary


def process_results(
    results,
    test_cases: List[LLMTestCase],
    queries: List[Dict],
    threshold: float,
    verbose: bool
) -> Dict[str, Any]:
    """Process evaluation results into summary."""

    # Extract scores from results.test_results (new DeepEval API)
    metric_scores = {
        "contextual_relevancy": [],
        "contextual_recall": [],
        "contextual_precision": []
    }

    per_query_results = []

    for i, test_result in enumerate(results.test_results):
        query_id = queries[i]["id"]
        query_result = {
            "query_id": query_id,
            "query": queries[i]["query"],
            "scores": {},
            "reasons": {}
        }

        # Get scores from metrics_data
        for metric_data in test_result.metrics_data:
            metric_name = metric_data.name
            score = metric_data.score if metric_data.score is not None else 0.0
            reason = metric_data.reason or ""

            # Map to our keys
            if "relevancy" in metric_name.lower():
                key = "contextual_relevancy"
            elif "recall" in metric_name.lower():
                key = "contextual_recall"
            elif "precision" in metric_name.lower():
                key = "contextual_precision"
            else:
                continue

            metric_scores[key].append(score)
            query_result["scores"][key] = score
            query_result["reasons"][key] = reason

        per_query_results.append(query_result)

    # Calculate averages
    avg_scores = {}
    for key, scores in metric_scores.items():
        avg_scores[key] = sum(scores) / len(scores) if scores else 0.0

    # Build summary
    summary = {
        "model": results.test_results[0].metrics_data[0].evaluation_model if results.test_results else "unknown",
        "total_queries": len(queries),
        "threshold": threshold,
        "metrics": {
            "contextual_relevancy": {
                "avg_score": avg_scores.get("contextual_relevancy", 0),
                "passed": avg_scores.get("contextual_relevancy", 0) >= threshold
            },
            "contextual_recall": {
                "avg_score": avg_scores.get("contextual_recall", 0),
                "passed": avg_scores.get("contextual_recall", 0) >= threshold
            },
            "contextual_precision": {
                "avg_score": avg_scores.get("contextual_precision", 0),
                "passed": avg_scores.get("contextual_precision", 0) >= threshold
            }
        },
        "per_query": per_query_results,
        "all_passed": all(m["passed"] for m in summary.get("metrics", {}).values()) if "metrics" in locals() else False
    }

    # Recalculate all_passed
    summary["all_passed"] = all(m["passed"] for m in summary["metrics"].values())

    if verbose:
        print_summary(summary)

    return summary


def print_summary(summary: Dict[str, Any]):
    """Print formatted evaluation summary."""
    print("\n" + "=" * 60)
    print("DEEPEVAL RETRIEVAL EVALUATION RESULTS")
    print("=" * 60)

    print(f"\nModel: {summary.get('model', 'unknown')}")
    print(f"Test Cases: {summary['total_queries']}")
    print(f"Threshold: {summary['threshold']}")

    print("\nMETRICS:")
    for metric_name, metric_data in summary["metrics"].items():
        score = metric_data["avg_score"]
        passed = metric_data["passed"]
        status = "PASS" if passed else "FAIL"
        print(f"  {metric_name}: {score:.2f} (threshold: {summary['threshold']}) [{status}]")

    print("\nBY QUERY:")
    for qr in summary["per_query"]:
        scores_str = ", ".join([
            f"{k.split('_')[1][:3]}={v:.2f}"
            for k, v in qr["scores"].items()
        ])
        print(f"  {qr['query_id']}: {scores_str}")

    # Show some reasons for lower scores
    print("\nSAMPLE REASONS (from LLM judge):")
    shown = 0
    for qr in summary["per_query"]:
        for metric, reason in qr["reasons"].items():
            if reason and qr["scores"].get(metric, 1.0) < summary["threshold"]:
                print(f"  {qr['query_id']} ({metric}):")
                print(f"    {reason[:200]}...")
                shown += 1
                if shown >= 3:
                    break
        if shown >= 3:
            break

    print("\n" + "=" * 60)
    if summary["all_passed"]:
        print("RESULT: ALL METRICS PASSED - Ready for generation pipeline")
    else:
        print("RESULT: SOME METRICS FAILED - Review retrieval quality")
    print("=" * 60)


def main():
    """Run evaluation and save results."""
    import argparse

    parser = argparse.ArgumentParser(description="Run DeepEval retrieval evaluation")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
    parser.add_argument("--threshold", type=float, default=0.7, help="Passing threshold")
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    # Run evaluation
    summary = run_deepeval_evaluation(
        top_k=args.top_k,
        threshold=args.threshold,
        verbose=not args.quiet
    )

    # Save results
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
