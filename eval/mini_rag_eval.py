#!/usr/bin/env python3
"""
Mini RAG Evaluation - Test DeepEval synthetic generation + evaluation on small subset.

Run: python eval/mini_rag_eval.py

This script:
1. Generates synthetic Q&A from 2-3 transcripts
2. Runs queries through our full pipeline (router → retrieval → synthesis)
3. Evaluates with DeepEval metrics (retrieval + synthesis quality)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from typing import List, Dict, Any

# DeepEval imports
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    AnswerRelevancyMetric,
)
from deepeval.synthesizer import Synthesizer
from deepeval.models import DeepEvalBaseLLM
import openai as openai_client

# Our pipeline imports
from scripts.retrieve_v2 import FocusGroupRetrieverV2, LLMRouter
from scripts.synthesize import FocusGroupSynthesizer
from eval.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, SYNTHESIS_MODEL, OPENROUTER_MODEL


# Custom OpenRouter model for DeepEval
class OpenRouterModel(DeepEvalBaseLLM):
    """Custom model that uses OpenRouter for DeepEval metrics."""

    def __init__(self, model: str = OPENROUTER_MODEL):
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
        # Sync fallback for async
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model


# Config
NUM_GOLDENS = 10  # Small test set
TRANSCRIPT_SUBSET = [
    "political-consulting-corpus/races/race-007-ohio-senate-2024/focus-groups/fg-001-cleveland-suburbs.md",
    "political-consulting-corpus/races/race-007-ohio-senate-2024/focus-groups/fg-003-youngstown-working-class.md",
]


def generate_synthetic_goldens(transcript_paths: List[str], num_goldens: int = 10) -> List[Dict]:
    """Generate synthetic test cases from transcripts using DeepEval Synthesizer."""
    print(f"\n📝 Generating {num_goldens} synthetic test cases from {len(transcript_paths)} transcripts...")

    synthesizer = Synthesizer()

    # Generate goldens from documents
    goldens = synthesizer.generate_goldens_from_docs(
        document_paths=transcript_paths,
        max_goldens_per_context=num_goldens // len(transcript_paths) + 1,
    )

    print(f"   Generated {len(goldens)} synthetic goldens")

    # Convert to our format
    test_cases = []
    for golden in goldens[:num_goldens]:
        test_cases.append({
            "query": golden.input,
            "expected_output": golden.expected_output,
            "context": golden.context,  # Retrieved context used to generate expected output
        })

    return test_cases


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
        # Get light summaries
        summaries = {}
        for fg_id, chunks in results_by_fg.items():
            if chunks:
                summaries[fg_id] = synthesizer.light_summary(chunks, query, fg_id)

        # If multiple FGs, do macro synthesis
        if len(summaries) > 1:
            output = synthesizer.macro_synthesis(
                fg_summaries=summaries,
                top_quotes=results_by_fg,
                query=query
            )
        else:
            # Single FG - use light summary
            output = list(summaries.values())[0] if summaries else "No relevant quotes found."
    else:
        output = "No relevant quotes found for this query."

    return {
        "output": output,
        "context": all_quotes,
        "selected_fgs": selected_fgs,
        "num_quotes": len(all_quotes),
    }


def create_test_cases(synthetic_data: List[Dict]) -> List[LLMTestCase]:
    """Run pipeline and create DeepEval test cases."""
    test_cases = []

    print(f"\n🔄 Running {len(synthetic_data)} queries through pipeline...")

    for i, data in enumerate(synthetic_data):
        query = data["query"]
        print(f"   [{i+1}/{len(synthetic_data)}] {query[:50]}...", end=" ", flush=True)

        try:
            result = run_pipeline(query)

            test_case = LLMTestCase(
                input=query,
                actual_output=result["output"],
                retrieval_context=result["context"],
                expected_output=data.get("expected_output"),
            )
            test_cases.append(test_case)
            print(f"✓ ({result['num_quotes']} quotes)")

        except Exception as e:
            print(f"✗ Error: {e}")
            continue

    return test_cases


def run_evaluation(test_cases: List[LLMTestCase]):
    """Run DeepEval metrics on test cases."""
    print(f"\n📊 Running DeepEval metrics on {len(test_cases)} test cases...")

    # Use OpenRouter model for evaluation (not OpenAI)
    # Note: Using gemini-flash as it has better JSON formatting for DeepEval
    eval_model = OpenRouterModel(model=OPENROUTER_MODEL)

    # Define metrics with custom model
    metrics = [
        ContextualRelevancyMetric(threshold=0.5, model=eval_model, async_mode=False),
        FaithfulnessMetric(threshold=0.5, model=eval_model, async_mode=False),
        AnswerRelevancyMetric(threshold=0.5, model=eval_model, async_mode=False),
    ]

    # Run evaluation
    results = evaluate(
        test_cases=test_cases,
        metrics=metrics,
    )

    return results


def main():
    print("=" * 60)
    print("Mini RAG Evaluation - DeepEval Synthetic Test")
    print("=" * 60)

    # Check transcripts exist
    for path in TRANSCRIPT_SUBSET:
        if not Path(path).exists():
            print(f"❌ Transcript not found: {path}")
            return

    # Step 1: Generate synthetic test cases
    try:
        synthetic_data = generate_synthetic_goldens(TRANSCRIPT_SUBSET, NUM_GOLDENS)
    except Exception as e:
        print(f"❌ Error generating synthetic data: {e}")
        print("   Falling back to manual test queries...")

        # Fallback: manual test queries
        synthetic_data = [
            {"query": "What did Cleveland voters say about jobs?", "expected_output": None},
            {"query": "How do working-class voters feel about Democrats?", "expected_output": None},
            {"query": "What concerns did Youngstown voters express about manufacturing?", "expected_output": None},
            {"query": "What did Ohio voters say about the economy?", "expected_output": None},
            {"query": "How do suburban voters feel about both parties?", "expected_output": None},
        ]

    # Save synthetic data for inspection
    output_file = Path(__file__).parent / "mini_eval_synthetic.json"
    with open(output_file, "w") as f:
        json.dump(synthetic_data, f, indent=2)
    print(f"\n💾 Saved synthetic queries to: {output_file}")

    # Step 2: Run through pipeline
    test_cases = create_test_cases(synthetic_data)

    if not test_cases:
        print("❌ No test cases created. Check pipeline errors above.")
        return

    # Step 3: Run DeepEval metrics
    try:
        results = run_evaluation(test_cases)
        print("\n✅ Evaluation complete!")
        print(f"   View results in DeepEval dashboard or check console output above.")
    except Exception as e:
        print(f"❌ Evaluation error: {e}")
        print("   This might be an API key or model configuration issue.")

        # Print raw results for debugging
        print("\n📋 Raw test case results:")
        for i, tc in enumerate(test_cases):
            print(f"\n--- Test Case {i+1} ---")
            print(f"Query: {tc.input[:80]}...")
            print(f"Output: {tc.actual_output[:200]}..." if tc.actual_output else "No output")
            print(f"Context items: {len(tc.retrieval_context) if tc.retrieval_context else 0}")


if __name__ == "__main__":
    main()
