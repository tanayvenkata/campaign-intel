#!/usr/bin/env python3
"""
Comprehensive RAG Evaluation - Full pipeline evaluation with diverse test set.

Run: python eval/comprehensive_rag_eval.py

This script:
1. Runs 40+ diverse test queries through the full pipeline
2. Evaluates with DeepEval metrics (retrieval + synthesis quality)
3. Outputs detailed results and aggregate metrics
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
from typing import List, Dict, Any
from datetime import datetime

# DeepEval imports
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    AnswerRelevancyMetric,
)
from deepeval.models import DeepEvalBaseLLM
import openai as openai_client

# Our pipeline imports
from scripts.retrieve_v2 import FocusGroupRetrieverV2, LLMRouter
from scripts.synthesize import FocusGroupSynthesizer
from eval.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL


class OpenRouterModel(DeepEvalBaseLLM):
    """Custom model that uses OpenRouter for DeepEval metrics."""

    def __init__(self, model: str = "google/gemini-2.0-flash-001"):
        self.model = model
        self.client = openai_client.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL
        )

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model


# Comprehensive test set covering all dimensions
COMPREHENSIVE_TEST_SET = [
    # ===== STATE-SPECIFIC QUERIES =====
    {"query": "What did Ohio voters say about the economy?", "category": "state-filter"},
    {"query": "How do Michigan voters feel about healthcare?", "category": "state-filter"},
    {"query": "What concerns did Pennsylvania voters express about jobs?",  "category": "state-filter"},
    {"query": "What did Wisconsin voters say about crime and safety?", "category": "state-filter"},
    {"query": "How do Georgia voters view the Democratic candidate?", "category": "state-filter"},
    {"query": "What did Arizona voters say about immigration?", "category": "state-filter"},
    {"query": "How do Nevada voters feel about cost of living?", "category": "state-filter"},
    {"query": "What issues matter most to Montana voters?", "category": "state-filter"},
    {"query": "What did North Carolina voters say about education?", "category": "state-filter"},

    # ===== DEMOGRAPHIC QUERIES =====
    {"query": "How do working-class voters feel about Democrats?", "category": "demographic"},
    {"query": "What concerns do suburban voters have about both parties?", "category": "demographic"},
    {"query": "What did Latino voters say about economic opportunity?", "category": "demographic"},
    {"query": "How do Black voters feel about representation?", "category": "demographic"},
    {"query": "What concerns do rural voters express about being ignored?", "category": "demographic"},
    {"query": "How do educated suburban voters view Republican candidates?", "category": "demographic"},
    {"query": "What do union members say about trade and jobs?", "category": "demographic"},
    {"query": "How do swing voters describe their indecision?", "category": "demographic"},

    # ===== CITY/LOCATION QUERIES =====
    {"query": "What did Cleveland voters say about manufacturing decline?", "category": "location"},
    {"query": "How do Detroit suburban voters feel about auto industry?",  "category": "location"},
    {"query": "What concerns did Philadelphia area voters express?", "category": "location"},
    {"query": "What did Pittsburgh voters say about economic transition?", "category": "location"},
    {"query": "How do Atlanta suburban voters view Democratic messaging?", "category": "location"},
    {"query": "What did Las Vegas voters say about housing costs?", "category": "location"},
    {"query": "How do Milwaukee suburban voters feel about crime?", "category": "location"},

    # ===== TOPIC-SPECIFIC (BROAD) QUERIES =====
    {"query": "What do voters say about inflation and prices?", "category": "topic-broad"},
    {"query": "How do voters feel about political polarization?", "category": "topic-broad"},
    {"query": "What frustrations do voters express about both parties?", "category": "topic-broad"},
    {"query": "What do voters say about healthcare costs?", "category": "topic-broad"},
    {"query": "How do voters describe their economic anxieties?", "category": "topic-broad"},
    {"query": "What messaging resonates with persuadable voters?", "category": "topic-broad"},
    {"query": "What do voters say about politicians being out of touch?",  "category": "topic-broad"},
    {"query": "How do voters feel about trade and tariffs?", "category": "topic-broad"},

    # ===== OUTCOME-BASED QUERIES =====
    {"query": "What went wrong in races we lost?", "category": "outcome"},
    {"query": "What messaging worked in winning campaigns?", "category": "outcome"},
    {"query": "Why did working-class voters defect in Ohio?", "category": "outcome"},
    {"query": "What did Montana voters say that led to our loss?", "category": "outcome"},
    {"query": "What was different about Wisconsin 2024 vs 2022?", "category": "outcome"},

    # ===== CROSS-RACE PATTERN QUERIES =====
    {"query": "What common concerns appear across Rust Belt states?", "category": "cross-race"},
    {"query": "How do economic concerns differ between suburban and rural voters?", "category": "cross-race"},
    {"query": "What patterns emerge in working-class sentiment across states?", "category": "cross-race"},
    {"query": "How does Latino voter sentiment compare between Arizona and Nevada?", "category": "cross-race"},

    # ===== SPECIFIC ANALYTICAL QUERIES =====
    {"query": "What authentic messaging connected with working-class voters?", "category": "analytical"},
    {"query": "How do voters describe feeling abandoned by Democrats?", "category": "analytical"},
    {"query": "What economic policies do swing voters want to hear about?", "category": "analytical"},
    {"query": "What candidate qualities matter most to suburban women?", "category": "analytical"},
]


def run_pipeline(query: str) -> Dict[str, Any]:
    """Run query through our full RAG pipeline."""
    retriever = FocusGroupRetrieverV2(use_router=True, use_reranker=True, verbose=False)
    router = LLMRouter()
    synthesizer = FocusGroupSynthesizer(verbose=False)

    # 1. Router - select relevant FGs
    selected_fgs = router.route(query)

    # 2. Retrieval - get quotes per FG
    results_by_fg = retriever.retrieve_per_focus_group(
        query,
        top_k_per_fg=5,
        score_threshold=0.7,
        filter_focus_groups=selected_fgs
    )

    # 3. Flatten quotes for context
    all_quotes = []
    for fg_id, chunks in results_by_fg.items():
        for chunk in chunks:
            all_quotes.append(chunk.content)

    # 4. Synthesis - generate summary
    if all_quotes:
        summaries = {}
        for fg_id, chunks in results_by_fg.items():
            if chunks:
                summaries[fg_id] = synthesizer.light_summary(chunks, query, fg_id)

        if len(summaries) > 1:
            output = synthesizer.macro_synthesis(
                fg_summaries=summaries,
                top_quotes=results_by_fg,
                query=query
            )
        else:
            output = list(summaries.values())[0] if summaries else "No relevant quotes found."
    else:
        output = "No relevant quotes found for this query."

    return {
        "output": output,
        "context": all_quotes,
        "selected_fgs": selected_fgs,
        "num_quotes": len(all_quotes),
        "num_fgs": len(results_by_fg),
    }


def create_test_cases(test_data: List[Dict]) -> List[tuple]:
    """Run pipeline and create DeepEval test cases."""
    test_cases = []
    pipeline_results = []

    print(f"\n{'='*60}")
    print(f"Running {len(test_data)} queries through pipeline...")
    print(f"{'='*60}\n")

    for i, data in enumerate(test_data):
        query = data["query"]
        category = data.get("category", "unknown")
        print(f"[{i+1:2d}/{len(test_data)}] [{category:12s}] {query[:50]}...", end=" ", flush=True)

        try:
            start_time = time.time()
            result = run_pipeline(query)
            elapsed = time.time() - start_time

            test_case = LLMTestCase(
                input=query,
                actual_output=result["output"],
                retrieval_context=result["context"],
                expected_output=data.get("expected_output"),
            )
            test_cases.append(test_case)

            pipeline_results.append({
                "query": query,
                "category": category,
                "num_quotes": result["num_quotes"],
                "num_fgs": result["num_fgs"],
                "selected_fgs": result["selected_fgs"],
                "output_preview": result["output"][:200] if result["output"] else "",
                "elapsed_seconds": round(elapsed, 2),
            })

            print(f"({result['num_quotes']} quotes, {result['num_fgs']} FGs, {elapsed:.1f}s)")

        except Exception as e:
            print(f"ERROR: {e}")
            pipeline_results.append({
                "query": query,
                "category": category,
                "error": str(e),
            })
            continue

    return test_cases, pipeline_results


def run_evaluation(test_cases: List[LLMTestCase]) -> Dict:
    """Run DeepEval metrics on test cases."""
    print(f"\n{'='*60}")
    print(f"Running DeepEval metrics on {len(test_cases)} test cases...")
    print(f"{'='*60}\n")

    eval_model = OpenRouterModel(model="google/gemini-2.0-flash-001")

    metrics = [
        ContextualRelevancyMetric(threshold=0.5, model=eval_model, async_mode=False),
        FaithfulnessMetric(threshold=0.5, model=eval_model, async_mode=False),
        AnswerRelevancyMetric(threshold=0.5, model=eval_model, async_mode=False),
    ]

    results = evaluate(
        test_cases=test_cases,
        metrics=metrics,
    )

    return results


def compute_summary_stats(test_cases: List[LLMTestCase], pipeline_results: List[Dict]) -> Dict:
    """Compute summary statistics."""
    # Category breakdown
    category_counts = {}
    for result in pipeline_results:
        cat = result.get("category", "unknown")
        if cat not in category_counts:
            category_counts[cat] = {"count": 0, "total_quotes": 0, "errors": 0}
        category_counts[cat]["count"] += 1
        if "error" in result:
            category_counts[cat]["errors"] += 1
        else:
            category_counts[cat]["total_quotes"] += result.get("num_quotes", 0)

    return {
        "total_queries": len(pipeline_results),
        "successful_queries": len(test_cases),
        "failed_queries": len(pipeline_results) - len(test_cases),
        "category_breakdown": category_counts,
        "avg_quotes_per_query": sum(r.get("num_quotes", 0) for r in pipeline_results if "error" not in r) / max(len(test_cases), 1),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-metrics", action="store_true", help="Skip DeepEval metrics, only run pipeline")
    parser.add_argument("--sample", type=int, default=0, help="Run on N random samples instead of full set")
    args = parser.parse_args()

    print("=" * 70)
    print("Comprehensive RAG Evaluation - Full Pipeline Test")
    print("=" * 70)

    test_data = COMPREHENSIVE_TEST_SET
    if args.sample > 0:
        import random
        test_data = random.sample(COMPREHENSIVE_TEST_SET, min(args.sample, len(COMPREHENSIVE_TEST_SET)))

    print(f"Test cases: {len(test_data)}")
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Step 1: Run through pipeline
    test_cases, pipeline_results = create_test_cases(test_data)

    if not test_cases:
        print("\nNo test cases created. Check pipeline errors above.")
        return

    # Step 2: Compute summary stats
    summary = compute_summary_stats(test_cases, pipeline_results)
    print(f"\n{'='*60}")
    print("Pipeline Summary")
    print(f"{'='*60}")
    print(f"Total queries: {summary['total_queries']}")
    print(f"Successful: {summary['successful_queries']}")
    print(f"Failed: {summary['failed_queries']}")
    print(f"Avg quotes/query: {summary['avg_quotes_per_query']:.1f}")
    print("\nBy category:")
    for cat, stats in summary['category_breakdown'].items():
        avg_quotes = stats['total_quotes'] / max(stats['count'] - stats['errors'], 1)
        print(f"  {cat:15s}: {stats['count']:2d} queries, {avg_quotes:.1f} avg quotes, {stats['errors']} errors")

    # Save pipeline results immediately
    output_dir = Path(__file__).parent / "comprehensive_results"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(output_dir / f"pipeline_results_{timestamp}.json", "w") as f:
        json.dump(pipeline_results, f, indent=2)
    with open(output_dir / f"summary_{timestamp}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nPipeline results saved to: {output_dir}")

    if args.skip_metrics:
        print("\nSkipping DeepEval metrics (--skip-metrics flag)")
        return

    # Step 3: Run DeepEval metrics
    print(f"\n{'='*60}")
    print("Running DeepEval metrics (this may take several minutes)...")
    print(f"{'='*60}\n")

    try:
        results = run_evaluation(test_cases)
        print("\nEvaluation complete!")
    except Exception as e:
        print(f"\nEvaluation error: {e}")
        print("Pipeline results were already saved.")


if __name__ == "__main__":
    main()
