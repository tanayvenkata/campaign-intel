#!/usr/bin/env python3
"""
HyDE: Hypothetical Document Embeddings
Generates hypothetical answers and embeds those instead of queries.
"""

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import OPENROUTER_API_KEY


class HyDE:
    """Hypothetical Document Embeddings for improved semantic search."""

    SYSTEM_PROMPT = """You are simulating a voter in a political focus group.

Given a search query about political topics, write a hypothetical quote that a voter might have said that would answer this query.

Rules:
- Write 2-3 sentences as if you are a real voter speaking in a focus group
- Use natural, conversational language
- Be specific and include concrete details
- Express genuine emotions and opinions
- Don't be overly polished - real voters ramble and use colloquial language

Example:
Query: "What did voters say about feeling abandoned by the party?"
Response: "Look, I've voted Democrat my whole life, but what have they done for us? They had decades to help this community and they didn't. The factories closed, jobs left, and nobody in Washington cared."

Return ONLY the hypothetical voter quote, nothing else."""

    def __init__(self, model: str = "openai/gpt-4o-mini", verbose: bool = False):
        import openai

        self.client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = model
        self.verbose = verbose

    def generate_hypothetical(self, query: str) -> str:
        """Generate a hypothetical voter quote for the query."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": query}
                ],
                max_tokens=200,
                temperature=0.7
            )

            hypothetical = response.choices[0].message.content.strip()

            if self.verbose:
                print(f"Query: {query}")
                print(f"Hypothetical: {hypothetical}")

            return hypothetical

        except Exception as e:
            if self.verbose:
                print(f"HyDE generation failed: {e}")
            return query  # Fallback to original query

    def search(self, query: str, retriever, top_k: int = 5) -> List:
        """
        Search using HyDE approach.

        1. Generate hypothetical document/answer
        2. Embed the hypothetical (not the query)
        3. Search for similar actual documents

        Args:
            query: Original search query
            retriever: FocusGroupRetrieverV2 instance
            top_k: Number of results to return

        Returns:
            List of RetrievalResult objects
        """
        # Generate hypothetical answer
        hypothetical = self.generate_hypothetical(query)

        # Use the hypothetical as the search query
        # The retriever will embed this and search
        # Note: We bypass the router for HyDE since we're searching by content similarity
        results = retriever.retrieve(hypothetical, top_k=top_k)

        return results


def main():
    """Test HyDE."""
    import argparse
    from scripts.retrieve_v2 import FocusGroupRetrieverV2

    parser = argparse.ArgumentParser(description="Test HyDE")
    parser.add_argument("query", nargs="?",
                        default="Show me moments where voters expressed distrust in institutions they used to support")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    print("Loading HyDE...")
    hyde = HyDE(verbose=True)

    print("Loading retriever...")
    retriever = FocusGroupRetrieverV2(use_router=True, verbose=False)

    print(f"\n{'='*60}")
    print(f"Query: {args.query}")
    print("=" * 60)

    # Generate hypothetical
    print("\nGenerating hypothetical voter quote...")
    hypothetical = hyde.generate_hypothetical(args.query)
    print(f"\nHypothetical: \"{hypothetical}\"")

    # Compare: regular search vs HyDE search
    print("\n" + "-" * 60)
    print("REGULAR SEARCH (embedding the query):")
    print("-" * 60)

    regular_results = retriever.retrieve(args.query, top_k=args.top_k)
    for i, r in enumerate(regular_results):
        print(f"\n{i+1}. [{r.focus_group_id}] (score: {r.score:.3f})")
        print(f"   {r.content[:150]}...")

    print("\n" + "-" * 60)
    print("HyDE SEARCH (embedding the hypothetical):")
    print("-" * 60)

    hyde_results = hyde.search(args.query, retriever, top_k=args.top_k)
    for i, r in enumerate(hyde_results):
        print(f"\n{i+1}. [{r.focus_group_id}] (score: {r.score:.3f})")
        print(f"   {r.content[:150]}...")


if __name__ == "__main__":
    main()
