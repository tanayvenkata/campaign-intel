#!/usr/bin/env python3
"""
Generate persistent demo cache for suggested queries.

This script runs the full pre-warming logic for all suggested queries
and saves the results to data/demo_cache.json. This file can then be
committed to the repo so demo queries never incur LLM costs.

Usage:
    python scripts/generate_demo_cache.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set production-like settings
os.environ.setdefault("USE_RERANKER", "false")
os.environ.setdefault("USE_OPENAI_EMBEDDINGS", "true")

from scripts.retrieve import FocusGroupRetrieverV2, LLMRouter, StrategyMemoRetriever
from scripts.synthesize import FocusGroupSynthesizer
from eval.config import STRATEGY_TOP_K_PER_RACE, USE_HYBRID_RETRIEVAL
from api.schemas import GroupedResult, StrategyGroupedResult, RetrievalChunk, StrategyChunk
from scripts.retrieve import RetrievalResult as ScriptRetrievalResult
import hashlib

# Same queries as in api/main.py
EXAMPLE_QUERIES = [
    "Ohio voters on economy",
    "What messaging mistakes did campaigns make?",
    "Where did Democratic messaging fail with union voters?",
    "What do swing voters want to hear about inflation?",
]

DEFAULT_TOP_K = 5
DEFAULT_SCORE_THRESHOLD = 0.50


def _get_cache_key(query: str, top_k: int, score_threshold: float, use_hybrid: bool = False) -> str:
    """Generate cache key from query parameters (same as api/main.py)."""
    raw = f"{query.lower().strip()}:{top_k}:{score_threshold}:{use_hybrid}"
    return hashlib.md5(raw.encode()).hexdigest()


def generate_query_cache(
    query: str,
    retriever: FocusGroupRetrieverV2,
    strategy_retriever: StrategyMemoRetriever,
    router: LLMRouter,
    synthesizer: FocusGroupSynthesizer
) -> dict:
    """Generate all cached data for a single query."""

    cache_key = _get_cache_key(query, DEFAULT_TOP_K, DEFAULT_SCORE_THRESHOLD, USE_HYBRID_RETRIEVAL)
    print(f"\n  Query: {query}")
    print(f"  Cache key: {cache_key}")

    # Route the query
    route_result = router.route_unified(query)
    content_type = route_result.content_type
    print(f"  Routed to: {content_type}")

    quotes_results = []
    lessons_results = []

    # Fetch focus group quotes if needed
    if content_type in ("quotes", "both"):
        fg_ids = route_result.focus_group_ids
        results_by_fg = retriever.retrieve_per_focus_group(
            query=query,
            top_k_per_fg=DEFAULT_TOP_K,
            score_threshold=DEFAULT_SCORE_THRESHOLD,
            filter_focus_groups=fg_ids
        )

        for fg_id, chunks in results_by_fg.items():
            if not chunks:
                continue
            top_score = max(c.score for c in chunks)
            if top_score < DEFAULT_SCORE_THRESHOLD:
                continue

            fg_meta = retriever._load_focus_group_metadata(fg_id)
            api_chunks = [
                RetrievalChunk(
                    chunk_id=c.chunk_id, score=c.score, content=c.content,
                    content_original=c.content_original, focus_group_id=c.focus_group_id,
                    participant=c.participant, participant_profile=c.participant_profile,
                    section=c.section, source_file=c.source_file, line_number=c.line_number,
                    preceding_moderator_q=c.preceding_moderator_q
                ) for c in chunks
            ]
            quotes_results.append(GroupedResult(
                focus_group_id=fg_id, focus_group_metadata=fg_meta, chunks=api_chunks
            ))
        print(f"  Found {len(quotes_results)} focus groups with quotes")

    # Fetch strategy lessons if needed
    if content_type in ("lessons", "both"):
        strategy_grouped = strategy_retriever.retrieve_grouped(
            query=query, top_k=STRATEGY_TOP_K_PER_RACE * 5,
            outcome_filter=route_result.outcome_filter, score_threshold=0.0
        )

        for group in strategy_grouped:
            top_chunks = sorted(group.chunks, key=lambda c: c.score, reverse=True)[:STRATEGY_TOP_K_PER_RACE]
            if not top_chunks or top_chunks[0].score < DEFAULT_SCORE_THRESHOLD:
                continue

            race_meta = strategy_retriever._get_race_metadata(group.race_id)
            api_chunks = [
                StrategyChunk(
                    chunk_id=c.chunk_id, score=c.score, content=c.content,
                    race_id=c.race_id, section=c.section, subsection=c.subsection,
                    outcome=c.outcome, state=c.state, year=c.year, margin=c.margin,
                    source_file=c.source_file, line_number=c.line_number
                ) for c in top_chunks
            ]
            lessons_results.append(StrategyGroupedResult(
                race_id=group.race_id, race_metadata=race_meta, chunks=api_chunks
            ))
        print(f"  Found {len(lessons_results)} races with lessons")

    # Build search results cache
    search_results = {
        "content_type": content_type,
        "quotes": [q.model_dump() for q in quotes_results],
        "lessons": [l.model_dump() for l in lessons_results],
        "stats": {
            "retrieval_time_ms": 0,
            "total_quotes": sum(len(g.chunks) for g in quotes_results),
            "total_lessons": sum(len(g.chunks) for g in lessons_results),
            "focus_groups_count": len(quotes_results),
            "races_count": len(lessons_results),
            "routed_to": content_type,
            "outcome_filter": route_result.outcome_filter,
            "cached": True,
            "prewarmed": True
        }
    }

    # Generate light summaries for focus groups
    light_summaries = {}
    deep_summaries = {}

    if quotes_results:
        fg_summaries_for_macro = {}
        fg_metadata_for_macro = {}
        top_quotes_for_macro = {}

        for fg in quotes_results:
            fg_id = fg.focus_group_id
            fg_metadata_for_macro[fg_id] = fg.focus_group_metadata

            # Convert chunks for synthesizer
            script_chunks = [
                ScriptRetrievalResult(
                    chunk_id=c.chunk_id, score=c.score, content=c.content,
                    content_original=c.content_original, focus_group_id=c.focus_group_id,
                    participant=c.participant, participant_profile=c.participant_profile,
                    section=c.section, source_file=c.source_file, line_number=c.line_number,
                    preceding_moderator_q=c.preceding_moderator_q or ""
                ) for c in fg.chunks
            ]
            top_quotes_for_macro[fg_id] = script_chunks

            # Generate light summary
            fg_name = fg.focus_group_metadata.get("location", fg_id)
            summary = synthesizer.light_summary(script_chunks, query, fg_name)
            light_summaries[fg_id] = summary
            fg_summaries_for_macro[fg_id] = summary
            print(f"    Light summary for {fg_id}: {len(summary)} chars")

            # Generate deep summary
            context = retriever.fetch_expanded_context(script_chunks, max_chunks=5)
            deep_result = synthesizer.deep_synthesis(script_chunks, context, query, fg_name)
            deep_summaries[fg_id] = deep_result
            print(f"    Deep summary for {fg_id}: {len(deep_result)} chars")

        # Generate macro synthesis if we have multiple FGs
        macro_synthesis = None
        if len(fg_summaries_for_macro) >= 2:
            macro_synthesis = synthesizer.light_macro_synthesis(
                fg_summaries=fg_summaries_for_macro,
                top_quotes=top_quotes_for_macro,
                fg_metadata=fg_metadata_for_macro,
                query=query
            )
            print(f"    Macro synthesis: {len(macro_synthesis)} chars")
    else:
        macro_synthesis = None

    # Generate strategy light summaries
    strategy_light = {}
    strategy_deep = {}

    if lessons_results:
        for race in lessons_results:
            race_id = race.race_id
            race_meta = race.race_metadata
            race_name = f"{race_meta.get('state', 'Unknown')} {race_meta.get('year', '?')}"

            # Build context from chunks
            chunks_text = []
            for c in race.chunks:
                chunks_text.append(f"[{c.section}] {c.content}")
            context = "\n\n".join(chunks_text)

            # Light summary
            prompt = f"""You are a senior political strategist summarizing campaign lessons.

Query: "{query}"
Race: {race_name}

Strategy memo excerpts:
{context}

Write a 1-2 sentence summary of the key lesson(s) from this race relevant to the query.
Be specific - include what worked/failed and why. No fluff."""

            try:
                response = synthesizer.client.chat.completions.create(
                    model=synthesizer.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    temperature=0.3
                )
                summary = response.choices[0].message.content.strip()
                strategy_light[race_id] = summary
                print(f"    Strategy light for {race_id}: {len(summary)} chars")
            except Exception as e:
                print(f"    Failed strategy light for {race_id}: {e}")

            # Deep summary
            deep_prompt = f"""You are a senior political strategist providing in-depth analysis.

Query: "{query}"
Race: {race_name}

Strategy memo excerpts:
{context}

Provide a 2-3 paragraph analysis of:
1. What the campaign did and why
2. What worked or failed
3. Key takeaways for future campaigns

Be specific and actionable. Reference specific tactics from the memo."""

            try:
                response = synthesizer.client.chat.completions.create(
                    model=synthesizer.model,
                    messages=[{"role": "user", "content": deep_prompt}],
                    max_tokens=500,
                    temperature=0.3
                )
                deep = response.choices[0].message.content.strip()
                strategy_deep[race_id] = deep
                print(f"    Strategy deep for {race_id}: {len(deep)} chars")
            except Exception as e:
                print(f"    Failed strategy deep for {race_id}: {e}")

    # Generate strategy macro if multiple races
    strategy_macro = None
    if len(strategy_light) >= 2:
        all_lessons = []
        for race_id, summary in strategy_light.items():
            race = next((r for r in lessons_results if r.race_id == race_id), None)
            if race:
                race_meta = race.race_metadata
                race_name = f"{race_meta.get('state', 'Unknown')} {race_meta.get('year', '?')}"
                all_lessons.append(f"**{race_name}**: {summary}")

        macro_prompt = f"""You are a senior political strategist synthesizing lessons across multiple campaigns.

Query: "{query}"

Individual race summaries:
{chr(10).join(all_lessons)}

Synthesize 2-3 key cross-cutting themes or patterns. What lessons emerge when looking across these campaigns together? Be specific."""

        try:
            response = synthesizer.client.chat.completions.create(
                model=synthesizer.model,
                messages=[{"role": "user", "content": macro_prompt}],
                max_tokens=400,
                temperature=0.3
            )
            strategy_macro = response.choices[0].message.content.strip()
            print(f"    Strategy macro: {len(strategy_macro)} chars")
        except Exception as e:
            print(f"    Failed strategy macro: {e}")

    return {
        "cache_key": cache_key,
        "search_results": search_results,
        "light_summaries": light_summaries,
        "deep_summaries": deep_summaries,
        "macro_synthesis": macro_synthesis,
        "strategy_light": strategy_light,
        "strategy_deep": strategy_deep,
        "strategy_macro": strategy_macro
    }


def main():
    print("=" * 60)
    print("Generating persistent demo cache")
    print("=" * 60)

    # Initialize resources (same as api/main.py lifespan)
    print("\nInitializing resources...")
    retriever = FocusGroupRetrieverV2(use_router=True, use_reranker=False, verbose=False)
    strategy_retriever = StrategyMemoRetriever(use_reranker=False, verbose=False)
    router = LLMRouter()
    synthesizer = FocusGroupSynthesizer(verbose=False)
    print("Resources initialized.")

    # Generate cache for each query
    demo_cache = {
        "queries": {},
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "version": "1.0"
    }

    for query in EXAMPLE_QUERIES:
        query_cache = generate_query_cache(
            query, retriever, strategy_retriever, router, synthesizer
        )
        demo_cache["queries"][query] = query_cache

    # Save to JSON
    output_path = project_root / "data" / "demo_cache.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(demo_cache, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Cache saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
