"""
Gemini 3 Flash via OpenRouter for DeepEval metrics.
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

# Import OpenAI client (OpenRouter is OpenAI-compatible)
import openai

# Import DeepEval base class
from deepeval.models import DeepEvalBaseLLM


class GeminiFlashJudge(DeepEvalBaseLLM):
    """
    Gemini 3 Flash via OpenRouter for DeepEval LLM-as-judge metrics.

    Uses OpenRouter's OpenAI-compatible API to access Gemini models.
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or OPENROUTER_MODEL
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )

    def load_model(self):
        """Return the model client."""
        return self.client

    def generate(self, prompt: str) -> str:
        """
        Generate response using Gemini via OpenRouter.

        Args:
            prompt: The prompt to send to the model

        Returns:
            The model's response text
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return response.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        """
        Async generate (falls back to sync for simplicity).

        DeepEval can use async for parallel evaluation, but we use sync
        as a fallback since OpenRouter doesn't require async.
        """
        return self.generate(prompt)

    def get_model_name(self) -> str:
        """Return the model name for logging."""
        return self.model_name


# Convenience function to create the judge
def get_judge_model(model_name: str = None) -> GeminiFlashJudge:
    """
    Get a configured Gemini Flash judge model.

    Args:
        model_name: Optional model name override

    Returns:
        GeminiFlashJudge instance
    """
    return GeminiFlashJudge(model_name=model_name)


if __name__ == "__main__":
    # Quick test
    judge = get_judge_model()
    print(f"Model: {judge.get_model_name()}")

    response = judge.generate("What is 2 + 2? Answer with just the number.")
    print(f"Response: {response}")
