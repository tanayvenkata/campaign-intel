#!/usr/bin/env python3
"""
Generate synthetic test queries from focus group chunks using DeepEval.
Focuses on Ohio 2024 chunks for the demo scenario.
"""

import json
import os
from pathlib import Path
from typing import List, Dict
import random

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    DATA_DIR,
    CHUNKS_DIR,
    OHIO_2024_FOCUS_GROUPS,
    EVAL_DIR
)

# Try to import deepeval, provide helpful error if not installed
try:
    from deepeval.synthesizer import Synthesizer
    from deepeval.models import DeepEvalBaseLLM
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False
    DeepEvalBaseLLM = object  # Placeholder for class definition
    print("DeepEval not installed. Using simple generation instead.")


class OpenRouterLLM(DeepEvalBaseLLM if DEEPEVAL_AVAILABLE else object):
    """Custom LLM wrapper for OpenRouter API."""

    def __init__(self, model: str = None):
        self.model = model or OPENROUTER_MODEL
        self._api_key = OPENROUTER_API_KEY

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        """Generate response using OpenRouter API."""
        import requests

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
            }
        )

        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.text}")

        return response.json()["choices"][0]["message"]["content"]

    async def a_generate(self, prompt: str) -> str:
        """Async generate (falls back to sync for simplicity)."""
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model


def load_ohio_2024_chunks() -> List[Dict]:
    """Load all chunks from Ohio 2024 focus groups."""
    chunks = []

    for fg_id in OHIO_2024_FOCUS_GROUPS:
        all_chunks_file = CHUNKS_DIR / fg_id / "all_chunks.json"
        if all_chunks_file.exists():
            with open(all_chunks_file) as f:
                fg_chunks = json.load(f)
                chunks.extend(fg_chunks)
                print(f"  Loaded {len(fg_chunks)} chunks from {fg_id}")

    return chunks


def generate_queries_simple(chunks: List[Dict], num_queries: int = 30) -> List[Dict]:
    """
    Generate synthetic queries using a simpler approach without DeepEval.
    Creates queries based on chunk content patterns.
    """
    queries = []

    # Query templates for V1 scope
    templates = [
        "What did voters say about {topic}?",
        "Show me quotes about {topic}.",
        "What did {location} voters think about {topic}?",
        "How did voters feel about {topic}?",
        "What concerns did voters express about {topic}?",
    ]

    # Extract topics from chunks
    topics_seen = set()
    for chunk in chunks:
        content = chunk["content"].lower()

        # Extract potential topics from content
        topic_keywords = {
            "economy": ["economy", "economic", "jobs", "wages", "money"],
            "inflation": ["inflation", "prices", "cost", "expensive", "afford"],
            "Democrats": ["democrat", "democratic", "party"],
            "Republicans": ["republican", "trump", "gop"],
            "Brennan": ["brennan", "tim", "senator"],
            "Stanton": ["stanton", "jim"],
            "unions": ["union", "uaw", "labor", "workers"],
            "manufacturing": ["factory", "plant", "manufacturing", "lordstown"],
            "healthcare": ["healthcare", "health care", "insurance", "medical"],
            "politicians": ["politician", "government", "washington", "columbus"],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in content for kw in keywords):
                topics_seen.add(topic)

    # Sample chunks and generate queries
    sampled_chunks = random.sample(chunks, min(num_queries, len(chunks)))

    for i, chunk in enumerate(sampled_chunks):
        template = random.choice(templates)
        location = chunk.get("focus_group_id", "").split("-")[-1].replace("-", " ").title()

        # Pick a topic that appears in this chunk
        content_lower = chunk["content"].lower()
        relevant_topics = []
        topic_keywords = {
            "the economy": ["economy", "economic", "jobs", "wages"],
            "inflation and prices": ["inflation", "prices", "cost", "afford"],
            "the Democratic party": ["democrat", "party left"],
            "Tim Brennan": ["brennan", "tim", "senator"],
            "Jim Stanton": ["stanton"],
            "unions and labor": ["union", "uaw", "labor"],
            "manufacturing jobs": ["factory", "plant", "manufacturing", "lordstown"],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in content_lower for kw in keywords):
                relevant_topics.append(topic)

        if not relevant_topics:
            relevant_topics = ["their concerns"]

        topic = random.choice(relevant_topics)

        query = template.format(topic=topic, location=location)

        queries.append({
            "id": f"synthetic-{i+1:03d}",
            "query": query,
            "category": "synthetic",
            "type": "auto_generated",
            "source_chunk_id": chunk["chunk_id"],
            "source_focus_group": chunk["focus_group_id"],
            "expected_content_snippet": chunk["content"][:100] + "...",
            "notes": "Auto-generated from chunk content"
        })

    return queries


def generate_queries_deepeval(chunks: List[Dict], num_queries: int = 30) -> List[Dict]:
    """Generate synthetic queries using DeepEval synthesizer."""
    if not DEEPEVAL_AVAILABLE:
        print("DeepEval not available, falling back to simple generation")
        return generate_queries_simple(chunks, num_queries)

    # Initialize LLM and synthesizer
    llm = OpenRouterLLM()
    synthesizer = Synthesizer(model=llm)

    # Prepare contexts from chunks
    contexts = []
    chunk_map = {}  # Map context index to chunk

    for i, chunk in enumerate(chunks[:num_queries]):
        context = f"Focus Group: {chunk['focus_group_id']}\n"
        context += f"Participant {chunk['participant']} ({chunk['participant_profile']}):\n"
        context += f"\"{chunk['content']}\""
        contexts.append([context])
        chunk_map[i] = chunk

    # Generate goldens (question-answer pairs)
    try:
        goldens = synthesizer.generate_goldens_from_contexts(
            contexts=contexts,
            max_goldens_per_context=1,
        )

        queries = []
        for i, golden in enumerate(goldens):
            chunk = chunk_map.get(i, {})
            queries.append({
                "id": f"synthetic-{i+1:03d}",
                "query": golden.input,
                "category": "synthetic",
                "type": "deepeval_generated",
                "source_chunk_id": chunk.get("chunk_id", ""),
                "source_focus_group": chunk.get("focus_group_id", ""),
                "expected_answer": golden.expected_output,
                "notes": "Generated by DeepEval synthesizer"
            })

        return queries

    except Exception as e:
        print(f"DeepEval generation failed: {e}")
        print("Falling back to simple generation")
        return generate_queries_simple(chunks, num_queries)


def merge_with_manual_queries(synthetic_queries: List[Dict]) -> Dict:
    """Merge synthetic queries with manual test queries."""
    manual_file = EVAL_DIR / "test_queries.json"

    with open(manual_file) as f:
        manual_data = json.load(f)

    # Add synthetic queries
    manual_data["queries"].extend(synthetic_queries)

    # Update metadata
    manual_data["metadata"]["synthetic_count"] = len(synthetic_queries)
    manual_data["metadata"]["total_count"] = len(manual_data["queries"])

    return manual_data


def main():
    print("=" * 60)
    print("Synthetic Query Generation")
    print("=" * 60)

    # Load Ohio 2024 chunks
    print("\nLoading Ohio 2024 chunks...")
    chunks = load_ohio_2024_chunks()
    print(f"Total chunks: {len(chunks)}")

    # Generate synthetic queries
    print("\nGenerating synthetic queries...")
    num_to_generate = 30

    # Try DeepEval first, fall back to simple if needed
    if DEEPEVAL_AVAILABLE:
        print("Using DeepEval synthesizer...")
        synthetic_queries = generate_queries_deepeval(chunks, num_to_generate)
    else:
        print("Using simple generation (DeepEval not installed)...")
        synthetic_queries = generate_queries_simple(chunks, num_to_generate)

    print(f"Generated {len(synthetic_queries)} synthetic queries")

    # Merge with manual queries
    print("\nMerging with manual test queries...")
    combined = merge_with_manual_queries(synthetic_queries)

    # Save combined file
    output_file = EVAL_DIR / "test_queries_combined.json"
    with open(output_file, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\nSaved combined queries to: {output_file}")
    print(f"Total queries: {combined['metadata']['total_count']}")

    # Summary by category
    categories = {}
    for q in combined["queries"]:
        cat = q["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
