"""
Strategy Retrieval Quality Optimization Testing

Tests different retrieval approaches for strategy memos:
1. Baseline (no reranker, threshold 0.50)
2. Reranking (cross-encoder re-scoring)
3. Top-K per race (no threshold)
4. HYDE (hypothetical document embedding)

Usage:
    python eval/test_strategy_retrieval_optimization.py --approach baseline
    python eval/test_strategy_retrieval_optimization.py --approach reranking
    python eval/test_strategy_retrieval_optimization.py --approach topk
    python eval/test_strategy_retrieval_optimization.py --approach hyde
    python eval/test_strategy_retrieval_optimization.py --all
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from statistics import mean
from typing import List, Dict, Any, Callable, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.retrieve import StrategyMemoRetriever, StrategyRetrievalResult
from eval.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

# Test queries with expected relevant races
TEST_QUERIES = [
    {
        "query": "What went wrong in Ohio 2024?",
        "expected_races": ["race-007"],
        "expected_sections": ["What Went Wrong", "Lessons for Ohio 2026", "The Collapse"]
    },
    {
        "query": "What economic messaging worked with working-class voters?",
        "expected_races": ["race-001", "race-002", "race-009"],  # Wins with economic messaging
        "expected_sections": ["What Worked", "Key Learnings"]
    },
    {
        "query": "Why did we lose Wisconsin 2022?",
        "expected_races": ["race-003"],
        "expected_sections": ["What Went Wrong", "Accountability Statement"]
    },
    {
        "query": "What worked for Latino voter outreach?",
        "expected_races": ["race-005", "race-006"],  # Arizona, Nevada
        "expected_sections": ["Latino", "What Worked"]
    },
    {
        "query": "Lessons from winning close races",
        "expected_races": ["race-005", "race-006"],  # Close wins (AZ +0.5%, NV +0.8%)
        "expected_sections": ["Margin Analysis", "Key Learnings"]
    }
]


def llm_judge_relevance(query: str, content: str) -> float:
    """
    Use LLM to judge if content is relevant to query.
    Returns score 0-1.
    """
    import openai

    client = openai.OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

    prompt = f"""Rate how relevant this strategy memo excerpt is to the query.
Score from 0 to 1:
- 1.0: Directly answers the query with specific insights
- 0.7: Relevant to the topic, provides useful context
- 0.4: Tangentially related, some overlap
- 0.0: Not relevant at all

Query: {query}

Content: {content[:500]}

Respond with ONLY a number between 0 and 1."""

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        score_text = response.choices[0].message.content.strip()
        return float(score_text)
    except Exception as e:
        print(f"LLM judge error: {e}")
        return 0.5


def evaluate_baseline(verbose: bool = True) -> Dict[str, Any]:
    """Evaluate baseline retrieval (no reranker, threshold 0.50)."""
    if verbose:
        print("\n" + "="*60)
        print("BASELINE: No reranker, threshold 0.50")
        print("="*60)

    retriever = StrategyMemoRetriever(use_reranker=False, verbose=False)

    results = []
    for test in TEST_QUERIES:
        query = test["query"]
        expected_races = test["expected_races"]

        start = time.time()
        chunks = retriever.retrieve(query, top_k=5)
        latency = (time.time() - start) * 1000

        # Check race coverage
        returned_races = set(c.race_id for c in chunks)
        race_recall = len(returned_races & set(expected_races)) / len(expected_races)

        # LLM-as-judge relevance
        relevance_scores = [llm_judge_relevance(query, c.content) for c in chunks]
        precision = mean(relevance_scores) if relevance_scores else 0

        if verbose:
            print(f"\nQuery: {query}")
            print(f"  Latency: {latency:.0f}ms")
            print(f"  Race recall: {race_recall:.1%} ({returned_races})")
            print(f"  Precision: {precision:.2f}")
            print(f"  Top chunks:")
            for c in chunks[:3]:
                print(f"    {c.score:.3f} | {c.race_id} | {c.section[:30]}")

        results.append({
            "query": query,
            "latency_ms": latency,
            "race_recall": race_recall,
            "precision": precision,
            "chunks": [{"score": c.score, "race_id": c.race_id, "section": c.section} for c in chunks]
        })

    summary = {
        "approach": "baseline",
        "avg_precision": mean([r["precision"] for r in results]),
        "avg_race_recall": mean([r["race_recall"] for r in results]),
        "avg_latency_ms": mean([r["latency_ms"] for r in results]),
        "details": results
    }

    if verbose:
        print(f"\n--- BASELINE SUMMARY ---")
        print(f"Avg Precision: {summary['avg_precision']:.2f}")
        print(f"Avg Race Recall: {summary['avg_race_recall']:.1%}")
        print(f"Avg Latency: {summary['avg_latency_ms']:.0f}ms")

    return summary


def evaluate_reranking(verbose: bool = True) -> Dict[str, Any]:
    """Evaluate with reranker enabled."""
    if verbose:
        print("\n" + "="*60)
        print("RERANKING: Cross-encoder re-scoring")
        print("="*60)

    retriever = StrategyMemoRetriever(use_reranker=True, verbose=False)

    results = []
    for test in TEST_QUERIES:
        query = test["query"]
        expected_races = test["expected_races"]

        start = time.time()
        chunks = retriever.retrieve(query, top_k=5)
        latency = (time.time() - start) * 1000

        returned_races = set(c.race_id for c in chunks)
        race_recall = len(returned_races & set(expected_races)) / len(expected_races)

        relevance_scores = [llm_judge_relevance(query, c.content) for c in chunks]
        precision = mean(relevance_scores) if relevance_scores else 0

        if verbose:
            print(f"\nQuery: {query}")
            print(f"  Latency: {latency:.0f}ms")
            print(f"  Race recall: {race_recall:.1%} ({returned_races})")
            print(f"  Precision: {precision:.2f}")
            print(f"  Top chunks:")
            for c in chunks[:3]:
                print(f"    {c.score:.3f} | {c.race_id} | {c.section[:30]}")

        results.append({
            "query": query,
            "latency_ms": latency,
            "race_recall": race_recall,
            "precision": precision,
            "chunks": [{"score": c.score, "race_id": c.race_id, "section": c.section} for c in chunks]
        })

    summary = {
        "approach": "reranking",
        "avg_precision": mean([r["precision"] for r in results]),
        "avg_race_recall": mean([r["race_recall"] for r in results]),
        "avg_latency_ms": mean([r["latency_ms"] for r in results]),
        "details": results
    }

    if verbose:
        print(f"\n--- RERANKING SUMMARY ---")
        print(f"Avg Precision: {summary['avg_precision']:.2f}")
        print(f"Avg Race Recall: {summary['avg_race_recall']:.1%}")
        print(f"Avg Latency: {summary['avg_latency_ms']:.0f}ms")

    return summary


def evaluate_topk(verbose: bool = True) -> Dict[str, Any]:
    """Evaluate top-K per race (no threshold filtering)."""
    if verbose:
        print("\n" + "="*60)
        print("TOP-K: Top 5 per race, no threshold")
        print("="*60)

    retriever = StrategyMemoRetriever(use_reranker=False, verbose=False)

    results = []
    for test in TEST_QUERIES:
        query = test["query"]
        expected_races = test["expected_races"]

        start = time.time()
        # Use retrieve_grouped with no threshold (set very low)
        grouped = retriever.retrieve_grouped(query, top_k=10, score_threshold=0.0)
        latency = (time.time() - start) * 1000

        # Flatten to top 5 overall
        all_chunks = []
        for group in grouped:
            all_chunks.extend(group.chunks[:3])  # Top 3 per race
        all_chunks = sorted(all_chunks, key=lambda c: c.score, reverse=True)[:5]

        returned_races = set(c.race_id for c in all_chunks)
        race_recall = len(returned_races & set(expected_races)) / len(expected_races)

        relevance_scores = [llm_judge_relevance(query, c.content) for c in all_chunks]
        precision = mean(relevance_scores) if relevance_scores else 0

        if verbose:
            print(f"\nQuery: {query}")
            print(f"  Latency: {latency:.0f}ms")
            print(f"  Race recall: {race_recall:.1%} ({returned_races})")
            print(f"  Precision: {precision:.2f}")
            print(f"  Top chunks:")
            for c in all_chunks[:3]:
                print(f"    {c.score:.3f} | {c.race_id} | {c.section[:30]}")

        results.append({
            "query": query,
            "latency_ms": latency,
            "race_recall": race_recall,
            "precision": precision,
            "chunks": [{"score": c.score, "race_id": c.race_id, "section": c.section} for c in all_chunks]
        })

    summary = {
        "approach": "topk",
        "avg_precision": mean([r["precision"] for r in results]),
        "avg_race_recall": mean([r["race_recall"] for r in results]),
        "avg_latency_ms": mean([r["latency_ms"] for r in results]),
        "details": results
    }

    if verbose:
        print(f"\n--- TOP-K SUMMARY ---")
        print(f"Avg Precision: {summary['avg_precision']:.2f}")
        print(f"Avg Race Recall: {summary['avg_race_recall']:.1%}")
        print(f"Avg Latency: {summary['avg_latency_ms']:.0f}ms")

    return summary


def evaluate_hyde(verbose: bool = True) -> Dict[str, Any]:
    """Evaluate HYDE (Hypothetical Document Embedding)."""
    if verbose:
        print("\n" + "="*60)
        print("HYDE: Hypothetical Document Embedding")
        print("="*60)

    import openai
    from sentence_transformers import SentenceTransformer
    from pinecone import Pinecone
    from eval.config import PINECONE_API_KEY, EMBEDDING_MODEL_LOCAL

    # Initialize components
    llm_client = openai.OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    embed_model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index("focus-group-v2")

    retriever = StrategyMemoRetriever(use_reranker=False, verbose=False)

    def generate_hypothetical(query: str) -> str:
        """Generate hypothetical strategy memo content for query."""
        prompt = f"""You are a political campaign strategist. Generate a brief hypothetical excerpt
from a campaign strategy memo that would answer this query.

Query: {query}

Write 2-3 sentences as if from an actual strategy memo analyzing campaign lessons.
Be specific with numbers, names, and insights. Start directly with the content."""

        response = llm_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()

    results = []
    for test in TEST_QUERIES:
        query = test["query"]
        expected_races = test["expected_races"]

        start = time.time()

        # Generate hypothetical document
        hypothetical = generate_hypothetical(query)

        # Embed hypothetical instead of query
        hyde_embedding = embed_model.encode(hypothetical).tolist()

        # Search with HYDE embedding
        search_results = index.query(
            vector=hyde_embedding,
            top_k=10,
            filter={"type": "strategy_memo"},
            include_metadata=True
        )

        # Convert to StrategyRetrievalResult
        chunks = []
        for match in search_results.matches[:5]:
            meta = match.metadata
            chunks.append(StrategyRetrievalResult(
                chunk_id=match.id,
                score=match.score,
                content=meta.get("content", ""),
                race_id=meta.get("race_id", ""),
                section=meta.get("section", ""),
                subsection=meta.get("subsection", ""),
                outcome=meta.get("outcome", ""),
                state=meta.get("state", ""),
                year=meta.get("year", 0),
                margin=meta.get("margin", 0.0),
                source_file=meta.get("source_file", ""),
                line_number=meta.get("line_number", 0),
            ))

        latency = (time.time() - start) * 1000

        returned_races = set(c.race_id for c in chunks)
        race_recall = len(returned_races & set(expected_races)) / len(expected_races)

        relevance_scores = [llm_judge_relevance(query, c.content) for c in chunks]
        precision = mean(relevance_scores) if relevance_scores else 0

        if verbose:
            print(f"\nQuery: {query}")
            print(f"  Hypothetical: {hypothetical[:80]}...")
            print(f"  Latency: {latency:.0f}ms")
            print(f"  Race recall: {race_recall:.1%} ({returned_races})")
            print(f"  Precision: {precision:.2f}")
            print(f"  Top chunks:")
            for c in chunks[:3]:
                print(f"    {c.score:.3f} | {c.race_id} | {c.section[:30]}")

        results.append({
            "query": query,
            "hypothetical": hypothetical,
            "latency_ms": latency,
            "race_recall": race_recall,
            "precision": precision,
            "chunks": [{"score": c.score, "race_id": c.race_id, "section": c.section} for c in chunks]
        })

    summary = {
        "approach": "hyde",
        "avg_precision": mean([r["precision"] for r in results]),
        "avg_race_recall": mean([r["race_recall"] for r in results]),
        "avg_latency_ms": mean([r["latency_ms"] for r in results]),
        "details": results
    }

    if verbose:
        print(f"\n--- HYDE SUMMARY ---")
        print(f"Avg Precision: {summary['avg_precision']:.2f}")
        print(f"Avg Race Recall: {summary['avg_race_recall']:.1%}")
        print(f"Avg Latency: {summary['avg_latency_ms']:.0f}ms")

    return summary


def print_comparison(results: List[Dict[str, Any]]):
    """Print comparison table of all approaches."""
    print("\n" + "="*70)
    print("COMPARISON TABLE")
    print("="*70)
    print(f"{'Approach':<15} {'Precision':<12} {'Race Recall':<14} {'Latency (ms)':<12}")
    print("-"*55)

    for r in results:
        print(f"{r['approach']:<15} {r['avg_precision']:<12.2f} {r['avg_race_recall']:<14.1%} {r['avg_latency_ms']:<12.0f}")

    # Decision recommendation
    print("\n--- RECOMMENDATION ---")
    baseline = next((r for r in results if r['approach'] == 'baseline'), None)

    for r in results:
        if r['approach'] == 'baseline':
            continue

        precision_delta = r['avg_precision'] - baseline['avg_precision']
        latency_delta = r['avg_latency_ms'] - baseline['avg_latency_ms']

        if r['approach'] == 'reranking':
            if precision_delta > 0.1 and latency_delta < 100:
                print(f"RERANKING: Recommend (precision +{precision_delta:.0%}, latency +{latency_delta:.0f}ms)")
            else:
                print(f"RERANKING: Not recommended (precision +{precision_delta:.0%}, latency +{latency_delta:.0f}ms)")

        elif r['approach'] == 'topk':
            if precision_delta >= 0:
                print(f"TOP-K: Recommend (quality maintained, simpler)")
            else:
                print(f"TOP-K: Not recommended (precision dropped {precision_delta:.0%})")

        elif r['approach'] == 'hyde':
            if precision_delta > 0.2:
                print(f"HYDE: Recommend (precision +{precision_delta:.0%} worth latency +{latency_delta:.0f}ms)")
            else:
                print(f"HYDE: Not recommended (precision +{precision_delta:.0%} not worth latency)")


def main():
    parser = argparse.ArgumentParser(description="Test strategy retrieval optimizations")
    parser.add_argument("--approach", choices=["baseline", "reranking", "topk", "hyde", "all"],
                        default="all", help="Which approach to test")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    args = parser.parse_args()

    verbose = not args.quiet
    results = []

    if args.approach in ("baseline", "all"):
        results.append(evaluate_baseline(verbose))

    if args.approach in ("reranking", "all"):
        results.append(evaluate_reranking(verbose))

    if args.approach in ("topk", "all"):
        results.append(evaluate_topk(verbose))

    if args.approach in ("hyde", "all"):
        results.append(evaluate_hyde(verbose))

    if len(results) > 1:
        print_comparison(results)

    # Save results
    output_file = Path(__file__).parent / "strategy_optimization_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
