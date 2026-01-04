#!/usr/bin/env python3
"""
Strategy memo retrieval evaluation.
Tests retrieval quality for campaign lessons and strategy content.

Uses LLM-as-judge to evaluate relevance of retrieved chunks.

Run: python eval/run_strategy_eval.py
     python eval/run_strategy_eval.py --verbose
     python eval/run_strategy_eval.py --category loss_analysis
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import (
    EVAL_DIR,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)


@dataclass
class QueryResult:
    """Result for a single query evaluation."""
    query_id: str
    query: str
    category: str
    passed: bool
    relevance_score: float  # Average LLM relevance score (0-1)
    race_recall: float  # % of expected races found
    section_recall: float  # % of expected sections found
    latency_ms: float
    num_results: int
    details: Dict[str, Any]


def load_test_queries() -> Dict:
    """Load strategy test queries."""
    query_file = EVAL_DIR / "test_queries_strategy.json"
    with open(query_file) as f:
        return json.load(f)


def judge_relevance(query: str, chunk_content: str, chunk_metadata: Dict) -> float:
    """
    Use LLM to judge relevance of a retrieved chunk.

    Returns: Score from 0.0 to 1.0
    """
    import openai

    client = openai.OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

    # Format metadata
    meta_str = f"Race: {chunk_metadata.get('state', '')} {chunk_metadata.get('year', '')} ({chunk_metadata.get('outcome', '')})"
    meta_str += f"\nSection: {chunk_metadata.get('section', '')}"
    if chunk_metadata.get('subsection'):
        meta_str += f" > {chunk_metadata.get('subsection', '')}"

    prompt = f"""Rate how relevant this retrieved chunk is to the user's query.

Query: {query}

Retrieved Chunk:
{meta_str}

Content:
{chunk_content[:800]}

Rate relevance from 0 to 10:
- 0-2: Not relevant at all
- 3-4: Slightly related topic but doesn't answer query
- 5-6: Somewhat relevant but missing key aspects
- 7-8: Relevant and useful
- 9-10: Highly relevant, directly answers query

Respond with ONLY a number from 0-10."""

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        score_text = response.choices[0].message.content.strip()
        # Extract number
        score = float(''.join(c for c in score_text if c.isdigit() or c == '.'))
        return min(score / 10.0, 1.0)  # Normalize to 0-1
    except Exception as e:
        print(f"  Warning: LLM judge error: {e}")
        return 0.5  # Default middle score on error


def evaluate_query(
    retriever,
    query_data: Dict,
    top_k: int = 5,
    use_llm_judge: bool = True,
    verbose: bool = False
) -> QueryResult:
    """Evaluate a single strategy query."""
    query_id = query_data["id"]
    query_text = query_data["query"]
    category = query_data["category"]

    # Get expected values
    expected_races = query_data.get("expected_races", [])
    expected_sections = query_data.get("expected_sections", [])
    outcome_filter = query_data.get("outcome_filter")
    state_filter = query_data.get("state_filter")

    # Time the retrieval
    start_time = time.time()
    results = retriever.retrieve(
        query_text,
        top_k=top_k,
        outcome_filter=outcome_filter,
        state_filter=state_filter
    )
    latency_ms = (time.time() - start_time) * 1000

    # Extract data from results
    retrieved_races = list(set(r.race_id for r in results))
    retrieved_sections = list(set(r.section for r in results))

    # Calculate race recall
    if expected_races:
        races_found = sum(1 for r in expected_races if r in retrieved_races)
        race_recall = races_found / len(expected_races)
    else:
        race_recall = 1.0  # No expectation = pass

    # Calculate section recall
    if expected_sections:
        sections_found = sum(1 for s in expected_sections if any(s.lower() in rs.lower() for rs in retrieved_sections))
        section_recall = sections_found / len(expected_sections)
    else:
        section_recall = 1.0

    # LLM relevance scoring
    relevance_scores = []
    if use_llm_judge and results:
        for r in results[:3]:  # Judge top 3 results
            chunk_metadata = {
                "state": r.state,
                "year": r.year,
                "outcome": r.outcome,
                "section": r.section,
                "subsection": r.subsection
            }
            score = judge_relevance(query_text, r.content, chunk_metadata)
            relevance_scores.append(score)
            if verbose:
                print(f"    [{score:.2f}] {r.race_id} | {r.section}")

    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

    # Determine pass/fail
    # Pass if: relevance >= 0.6 AND (race_recall >= 0.5 OR section_recall >= 0.5)
    passed = avg_relevance >= 0.6 and (race_recall >= 0.5 or section_recall >= 0.5)

    return QueryResult(
        query_id=query_id,
        query=query_text,
        category=category,
        passed=passed,
        relevance_score=avg_relevance,
        race_recall=race_recall,
        section_recall=section_recall,
        latency_ms=latency_ms,
        num_results=len(results),
        details={
            "expected_races": expected_races,
            "retrieved_races": retrieved_races,
            "expected_sections": expected_sections,
            "retrieved_sections": retrieved_sections,
            "relevance_scores": relevance_scores,
        }
    )


def run_evaluation(
    category_filter: Optional[str] = None,
    use_llm_judge: bool = True,
    verbose: bool = False
) -> Dict[str, Any]:
    """Run full evaluation suite."""
    from scripts.retrieve import StrategyMemoRetriever

    print("=" * 60)
    print("STRATEGY MEMO RETRIEVAL EVALUATION")
    print("=" * 60)

    # Load retriever
    print("\nLoading StrategyMemoRetriever...")
    retriever = StrategyMemoRetriever(verbose=False)

    # Load test queries
    test_data = load_test_queries()
    queries = test_data["queries"]

    # Filter by category if specified
    if category_filter:
        queries = [q for q in queries if q["category"] == category_filter]
        print(f"Filtered to {len(queries)} queries in category: {category_filter}")
    else:
        print(f"Running {len(queries)} queries")

    # Run evaluations
    results: List[QueryResult] = []

    for i, query_data in enumerate(queries):
        if verbose:
            print(f"\n[{i+1}/{len(queries)}] {query_data['id']}: {query_data['query']}")
        else:
            print(f"  [{i+1}/{len(queries)}] {query_data['id']}...", end=" ")

        result = evaluate_query(
            retriever,
            query_data,
            use_llm_judge=use_llm_judge,
            verbose=verbose
        )
        results.append(result)

        if not verbose:
            status = "PASS" if result.passed else "FAIL"
            print(f"{status} (rel={result.relevance_score:.2f}, race={result.race_recall:.2f})")

    # Aggregate results
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    # By category
    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = {"total": 0, "passed": 0, "relevance": []}
        categories[r.category]["total"] += 1
        if r.passed:
            categories[r.category]["passed"] += 1
        categories[r.category]["relevance"].append(r.relevance_score)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nOverall: {passed}/{total} passed ({100*passed/total:.1f}%)")
    print(f"Average relevance: {sum(r.relevance_score for r in results)/total:.2f}")
    print(f"Average latency: {sum(r.latency_ms for r in results)/total:.0f}ms")

    print("\nBy Category:")
    for cat, stats in sorted(categories.items()):
        avg_rel = sum(stats["relevance"]) / len(stats["relevance"])
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({avg_rel:.2f} avg relevance)")

    # Print failures
    failures = [r for r in results if not r.passed]
    if failures:
        print(f"\nFailed Queries ({len(failures)}):")
        for r in failures:
            print(f"  - {r.query_id}: rel={r.relevance_score:.2f}, race_recall={r.race_recall:.2f}")

    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total > 0 else 0,
        "avg_relevance": sum(r.relevance_score for r in results) / total if total > 0 else 0,
        "avg_latency_ms": sum(r.latency_ms for r in results) / total if total > 0 else 0,
        "by_category": {
            cat: {
                "pass_rate": stats["passed"] / stats["total"],
                "avg_relevance": sum(stats["relevance"]) / len(stats["relevance"])
            }
            for cat, stats in categories.items()
        },
        "results": [asdict(r) for r in results]
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Strategy memo retrieval evaluation")
    parser.add_argument("--category", type=str, help="Filter to specific category")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM judge (faster but less accurate)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", type=str, help="Save results to JSON file")

    args = parser.parse_args()

    results = run_evaluation(
        category_filter=args.category,
        use_llm_judge=not args.no_llm,
        verbose=args.verbose
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
