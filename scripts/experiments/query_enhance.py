#!/usr/bin/env python3
"""
Query Enhancement: LLM-based synonym expansion for semantic search.
Expands queries with domain-specific synonyms before embedding.
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import OPENROUTER_API_KEY


class QueryEnhancer:
    """Expand search queries with synonyms using LLM."""

    SYSTEM_PROMPT = """You are a search query expander for a political focus group database.

Given a user's search query, expand it with synonyms and related phrases that voters might use.

Rules:
- Add 3-5 alternative phrasings that capture the same intent
- Use language that real voters would use in focus groups
- Keep the expansion concise (under 100 words total)
- Return the original query plus expansions as a single search string
- Focus on semantic variations, not just synonyms

Examples:
- "feeling abandoned by the party" → "feeling abandoned by the party, left behind by Democrats, party didn't help us, neglected by politicians, betrayed by leadership"
- "economy concerns" → "economy concerns, cost of living, inflation, can't afford groceries, prices too high, struggling to make ends meet"
- "distrust in institutions" → "distrust in institutions, lost faith in government, don't trust politicians, system is broken, nobody listens to us"

Return ONLY the expanded query string, no explanation."""

    def __init__(self, model: str = "openai/gpt-4o-mini", verbose: bool = False):
        import openai

        self.client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = model
        self.verbose = verbose

    def expand(self, query: str) -> str:
        """Expand query with synonyms and related phrases."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": query}
                ],
                max_tokens=200,
                temperature=0.3
            )

            expanded = response.choices[0].message.content.strip()

            if self.verbose:
                print(f"Original: {query}")
                print(f"Expanded: {expanded}")

            return expanded

        except Exception as e:
            if self.verbose:
                print(f"Enhancement failed: {e}, using original query")
            return query


def main():
    """Test query enhancement."""
    import argparse

    parser = argparse.ArgumentParser(description="Test query enhancement")
    parser.add_argument("query", nargs="?", help="Query to enhance")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    enhancer = QueryEnhancer(verbose=True)

    if args.query:
        enhanced = enhancer.expand(args.query)
        print(f"\nResult: {enhanced}")
    else:
        # Test with failing semantic queries
        test_queries = [
            "Show me moments where voters expressed distrust in institutions they used to support",
            "Show me quotes about feeling abandoned by the party",
            "What did voters say about the economy?",
            "How did working-class voters feel about Democrats?",
        ]

        print("Query Enhancement Test")
        print("=" * 60)

        for query in test_queries:
            print(f"\n{query}")
            print("-" * 40)
            enhanced = enhancer.expand(query)
            print(f"→ {enhanced}\n")


if __name__ == "__main__":
    main()
