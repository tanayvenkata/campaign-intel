#!/usr/bin/env python3
"""
Doc2Query: Expand documents with generated search queries at index time.
This is the "reverse" of query expansion - we expand documents, not queries.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import OPENROUTER_API_KEY, DATA_DIR


class Doc2Query:
    """Generate search queries for documents to improve retrieval."""

    SYSTEM_PROMPT = """Given this voter quote from a political focus group, generate 3 search queries that someone might use to find this quote.

Think about:
- What topics does this quote address?
- What emotions or sentiments does it express?
- What would a researcher searching for this type of content type?

Return ONLY the 3 queries, one per line. No numbering, no explanation."""

    def __init__(self, model: str = "openai/gpt-4o-mini", verbose: bool = False):
        import openai

        self.client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = model
        self.verbose = verbose

    def generate_queries(self, content: str) -> List[str]:
        """Generate search queries for a document."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": content}
                ],
                max_tokens=150,
                temperature=0.3
            )

            queries_text = response.choices[0].message.content.strip()
            queries = [q.strip() for q in queries_text.split("\n") if q.strip()]

            if self.verbose:
                print(f"Content: {content[:100]}...")
                print(f"Queries: {queries}")

            return queries[:3]  # Limit to 3

        except Exception as e:
            if self.verbose:
                print(f"Query generation failed: {e}")
            return []

    def expand_document(self, content: str) -> str:
        """Expand document with generated queries."""
        queries = self.generate_queries(content)
        if queries:
            queries_text = " | ".join(queries)
            return f"{content}\n\n[Search queries: {queries_text}]"
        return content


def expand_all_chunks(
    output_dir: Path,
    max_chunks: int = None,
    batch_size: int = 10,
    verbose: bool = True
):
    """Expand all chunks with Doc2Query and save to new directory."""
    from eval.config import DATA_DIR

    chunks_dir = DATA_DIR / "chunks_enriched"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc2query = Doc2Query(verbose=False)

    # Load all chunks
    all_chunks = []
    for fg_dir in sorted(chunks_dir.iterdir()):
        if fg_dir.is_dir():
            chunks_file = fg_dir / "all_chunks.json"
            if chunks_file.exists():
                with open(chunks_file) as f:
                    chunks = json.load(f)
                    all_chunks.extend(chunks)

    if max_chunks:
        all_chunks = all_chunks[:max_chunks]

    print(f"Expanding {len(all_chunks)} chunks with Doc2Query...")
    print(f"Output directory: {output_dir}")

    expanded_chunks = []
    start_time = time.time()

    for i, chunk in enumerate(all_chunks):
        content = chunk.get("content", chunk.get("content_original", ""))

        # Generate queries and expand
        expanded_content = doc2query.expand_document(content)

        # Create new chunk with expanded content
        expanded_chunk = chunk.copy()
        expanded_chunk["content_doc2query"] = expanded_content
        expanded_chunk["content_original"] = chunk.get("content_original", content)
        expanded_chunks.append(expanded_chunk)

        # Progress
        if verbose and (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(all_chunks) - i - 1) / rate
            print(f"  [{i+1}/{len(all_chunks)}] {rate:.1f} chunks/sec, ~{remaining/60:.1f} min remaining")

    # Save expanded chunks
    output_file = output_dir / "all_chunks_doc2query.json"
    with open(output_file, "w") as f:
        json.dump(expanded_chunks, f, indent=2)

    print(f"\nSaved {len(expanded_chunks)} expanded chunks to {output_file}")
    print(f"Total time: {(time.time() - start_time)/60:.1f} minutes")

    return expanded_chunks


def main():
    """Run Doc2Query expansion."""
    import argparse

    parser = argparse.ArgumentParser(description="Expand documents with Doc2Query")
    parser.add_argument("--output", default="data/chunks_doc2query",
                        help="Output directory for expanded chunks")
    parser.add_argument("--max-chunks", type=int, help="Limit number of chunks (for testing)")
    parser.add_argument("--test", action="store_true", help="Test on a few samples")

    args = parser.parse_args()

    if args.test:
        # Test on a few samples
        doc2query = Doc2Query(verbose=True)

        test_contents = [
            "Democrats had decades to help us and they didn't. The factories closed and nobody cared.",
            "I used to be a Democrat, but they left us behind. Now I vote Republican.",
            "The economy is terrible. Everything costs more and my paycheck is the same.",
        ]

        print("Doc2Query Test")
        print("=" * 60)

        for content in test_contents:
            print(f"\nContent: {content}")
            print("-" * 40)
            queries = doc2query.generate_queries(content)
            for q in queries:
                print(f"  → {q}")
            print()
    else:
        expand_all_chunks(
            output_dir=Path(args.output),
            max_chunks=args.max_chunks,
            verbose=True
        )


if __name__ == "__main__":
    main()
