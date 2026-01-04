#!/usr/bin/env python3
"""
Macro Synthesis A/B Evaluation

Compares Light Macro vs Deep Macro synthesis on broad queries.
Tracks: latency, token cost, quality metrics.

Run: python eval/macro_synthesis_eval.py
"""

import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.retrieve import FocusGroupRetrieverV2, LLMRouter
from scripts.synthesize import FocusGroupSynthesizer, RetrievalResult
from eval.config import DATA_DIR, FOCUS_GROUPS_DIR


# Test queries - "topic-broad" category from comprehensive_rag_eval.py
BROAD_QUERIES = [
    "What do voters say about inflation and prices?",
    "How do voters feel about political polarization?",
    "What frustrations do voters express about both parties?",
    "What do voters say about healthcare costs?",
    "How do voters describe their economic anxieties?",
    "What messaging resonates with persuadable voters?",
    "What do voters say about politicians being out of touch?",
    "How do voters feel about trade and tariffs?",
]


@dataclass
class SynthesisResult:
    """Result from a single synthesis run."""
    query: str
    mode: str  # "light" or "deep"
    output: str
    themes: Optional[List[Dict]] = None  # Only for deep mode
    latency_ms: float = 0
    llm_calls: int = 0
    focus_groups_count: int = 0
    quotes_count: int = 0
    error: Optional[str] = None


def load_fg_metadata(fg_id: str) -> Dict[str, Any]:
    """Load focus group metadata from file."""
    fg_file = FOCUS_GROUPS_DIR / f"{fg_id}.json"
    if fg_file.exists():
        with open(fg_file) as f:
            data = json.load(f)
            return {
                "location": data.get("location", "Unknown"),
                "race_name": data.get("race_name", "Unknown race"),
                "outcome": data.get("outcome", "unknown"),
                "participant_summary": data.get("participant_summary", ""),
            }
    return {"location": "Unknown", "race_name": "Unknown", "outcome": "unknown"}


def run_pipeline(query: str, mode: str, retriever: FocusGroupRetrieverV2, synthesizer: FocusGroupSynthesizer) -> SynthesisResult:
    """Run full pipeline: retrieval -> synthesis."""

    # 1. Retrieve (same for both modes)
    print(f"  Retrieving for: {query[:50]}...")
    results_by_fg = retriever.retrieve_per_focus_group(query, top_k_per_fg=5, score_threshold=0.7)

    if not results_by_fg:
        return SynthesisResult(
            query=query,
            mode=mode,
            output="",
            error="No results retrieved"
        )

    # 2. Generate light summaries
    print(f"  Generating light summaries for {len(results_by_fg)} focus groups...")
    fg_summaries = {}
    for fg_id, chunks in results_by_fg.items():
        if chunks:
            summary = synthesizer.light_summary(chunks, query, fg_id)
            fg_summaries[fg_id] = summary

    # 3. Load metadata
    fg_metadata = {}
    for fg_id in results_by_fg.keys():
        fg_metadata[fg_id] = load_fg_metadata(fg_id)

    # 4. Count quotes
    total_quotes = sum(len(chunks) for chunks in results_by_fg.values())

    # 5. Macro synthesis (differs by mode)
    print(f"  Running {mode} macro synthesis...")
    start_time = time.time()

    try:
        if mode == "light":
            output = synthesizer.light_macro_synthesis(
                fg_summaries=fg_summaries,
                top_quotes=results_by_fg,
                fg_metadata=fg_metadata,
                query=query
            )
            latency_ms = (time.time() - start_time) * 1000

            return SynthesisResult(
                query=query,
                mode=mode,
                output=output,
                latency_ms=latency_ms,
                llm_calls=1 + len(fg_summaries),  # 1 macro + N light summaries
                focus_groups_count=len(results_by_fg),
                quotes_count=total_quotes
            )
        else:
            result = synthesizer.deep_macro_synthesis(
                fg_summaries=fg_summaries,
                top_quotes=results_by_fg,
                fg_metadata=fg_metadata,
                query=query
            )
            latency_ms = (time.time() - start_time) * 1000

            # Format output for display
            output_parts = []
            for theme in result.get("themes", []):
                output_parts.append(f"**{theme['name']}**\n{theme['synthesis']}")
            output = "\n\n---\n\n".join(output_parts)

            metadata = result.get("metadata", {})

            return SynthesisResult(
                query=query,
                mode=mode,
                output=output,
                themes=result.get("themes", []),
                latency_ms=latency_ms,
                llm_calls=metadata.get("llm_calls", 0) + len(fg_summaries),
                focus_groups_count=len(results_by_fg),
                quotes_count=total_quotes,
                error=metadata.get("error")
            )
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return SynthesisResult(
            query=query,
            mode=mode,
            output="",
            latency_ms=latency_ms,
            llm_calls=len(fg_summaries),
            focus_groups_count=len(results_by_fg),
            quotes_count=total_quotes,
            error=str(e)
        )


def calculate_metrics(results: List[SynthesisResult]) -> Dict[str, Any]:
    """Calculate aggregate metrics for a set of results."""
    successful = [r for r in results if not r.error]

    if not successful:
        return {"error": "All queries failed"}

    avg_latency = sum(r.latency_ms for r in successful) / len(successful)
    avg_llm_calls = sum(r.llm_calls for r in successful) / len(successful)
    avg_output_length = sum(len(r.output) for r in successful) / len(successful)

    # For deep mode, count themes
    theme_counts = [len(r.themes) for r in successful if r.themes]
    avg_themes = sum(theme_counts) / len(theme_counts) if theme_counts else 0

    return {
        "total_queries": len(results),
        "successful_queries": len(successful),
        "failed_queries": len(results) - len(successful),
        "avg_latency_ms": round(avg_latency),
        "avg_llm_calls": round(avg_llm_calls, 1),
        "avg_output_chars": round(avg_output_length),
        "avg_themes": round(avg_themes, 1) if avg_themes else None,
        "avg_fgs_per_query": round(sum(r.focus_groups_count for r in successful) / len(successful), 1),
        "avg_quotes_per_query": round(sum(r.quotes_count for r in successful) / len(successful), 1),
    }


def print_comparison(light_metrics: Dict, deep_metrics: Dict):
    """Print side-by-side comparison of metrics."""
    print("\n" + "=" * 70)
    print("COMPARISON: Light Macro vs Deep Macro")
    print("=" * 70)

    print(f"\n{'Metric':<30} {'Light':<20} {'Deep':<20}")
    print("-" * 70)

    metrics_to_compare = [
        ("Successful Queries", "successful_queries"),
        ("Avg Latency (ms)", "avg_latency_ms"),
        ("Avg LLM Calls", "avg_llm_calls"),
        ("Avg Output Length (chars)", "avg_output_chars"),
        ("Avg Themes Discovered", "avg_themes"),
        ("Avg Focus Groups", "avg_fgs_per_query"),
        ("Avg Quotes", "avg_quotes_per_query"),
    ]

    for label, key in metrics_to_compare:
        light_val = light_metrics.get(key, "N/A")
        deep_val = deep_metrics.get(key, "N/A")
        print(f"{label:<30} {str(light_val):<20} {str(deep_val):<20}")

    # Calculate relative differences
    print("\n" + "-" * 70)
    print("KEY INSIGHTS:")

    if light_metrics.get("avg_latency_ms") and deep_metrics.get("avg_latency_ms"):
        latency_ratio = deep_metrics["avg_latency_ms"] / light_metrics["avg_latency_ms"]
        print(f"  - Deep is {latency_ratio:.1f}x slower than Light")

    if light_metrics.get("avg_llm_calls") and deep_metrics.get("avg_llm_calls"):
        calls_ratio = deep_metrics["avg_llm_calls"] / light_metrics["avg_llm_calls"]
        print(f"  - Deep uses {calls_ratio:.1f}x more LLM calls")

    if light_metrics.get("avg_output_chars") and deep_metrics.get("avg_output_chars"):
        length_ratio = deep_metrics["avg_output_chars"] / light_metrics["avg_output_chars"]
        print(f"  - Deep produces {length_ratio:.1f}x more content")


def save_results(light_results: List[SynthesisResult], deep_results: List[SynthesisResult],
                 light_metrics: Dict, deep_metrics: Dict):
    """Save detailed results to JSON."""
    results_dir = Path(__file__).parent / "macro_synthesis_results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save detailed results
    detailed = {
        "timestamp": timestamp,
        "queries": BROAD_QUERIES,
        "light_results": [asdict(r) for r in light_results],
        "deep_results": [asdict(r) for r in deep_results],
        "light_metrics": light_metrics,
        "deep_metrics": deep_metrics,
    }

    results_file = results_dir / f"comparison_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump(detailed, f, indent=2)

    print(f"\nResults saved to: {results_file}")

    # Also save a summary
    summary_file = results_dir / f"summary_{timestamp}.txt"
    with open(summary_file, "w") as f:
        f.write("MACRO SYNTHESIS COMPARISON RESULTS\n")
        f.write(f"Run: {timestamp}\n")
        f.write(f"Queries tested: {len(BROAD_QUERIES)}\n\n")

        f.write("LIGHT MACRO METRICS:\n")
        for k, v in light_metrics.items():
            f.write(f"  {k}: {v}\n")

        f.write("\nDEEP MACRO METRICS:\n")
        for k, v in deep_metrics.items():
            f.write(f"  {k}: {v}\n")

        f.write("\n\nSAMPLE OUTPUTS:\n")
        f.write("=" * 70 + "\n")

        if light_results and light_results[0].output:
            f.write(f"\nLIGHT - Query: {light_results[0].query}\n")
            f.write("-" * 40 + "\n")
            f.write(light_results[0].output[:1000] + "...\n")

        if deep_results and deep_results[0].output:
            f.write(f"\nDEEP - Query: {deep_results[0].query}\n")
            f.write("-" * 40 + "\n")
            f.write(deep_results[0].output[:1000] + "...\n")

    print(f"Summary saved to: {summary_file}")


def main():
    print("=" * 70)
    print("MACRO SYNTHESIS COMPARISON EVALUATION")
    print("=" * 70)
    print(f"Testing {len(BROAD_QUERIES)} broad queries")
    print()

    # Initialize components
    print("Initializing retriever and synthesizer...")
    retriever = FocusGroupRetrieverV2(use_router=True, use_reranker=True, verbose=False)
    synthesizer = FocusGroupSynthesizer(verbose=True)

    light_results: List[SynthesisResult] = []
    deep_results: List[SynthesisResult] = []

    for i, query in enumerate(BROAD_QUERIES):
        print(f"\n[{i+1}/{len(BROAD_QUERIES)}] Query: {query}")
        print("-" * 50)

        # Run light macro
        print("\n  [LIGHT MODE]")
        light_result = run_pipeline(query, "light", retriever, synthesizer)
        light_results.append(light_result)
        print(f"  Latency: {light_result.latency_ms:.0f}ms, LLM calls: {light_result.llm_calls}, FGs: {light_result.focus_groups_count}")
        if light_result.error:
            print(f"  ERROR: {light_result.error}")

        # Run deep macro
        print("\n  [DEEP MODE]")
        deep_result = run_pipeline(query, "deep", retriever, synthesizer)
        deep_results.append(deep_result)
        print(f"  Latency: {deep_result.latency_ms:.0f}ms, LLM calls: {deep_result.llm_calls}, Themes: {len(deep_result.themes or [])}")
        if deep_result.error:
            print(f"  ERROR: {deep_result.error}")

    # Calculate metrics
    light_metrics = calculate_metrics(light_results)
    deep_metrics = calculate_metrics(deep_results)

    # Print comparison
    print_comparison(light_metrics, deep_metrics)

    # Save results
    save_results(light_results, deep_results, light_metrics, deep_metrics)

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
