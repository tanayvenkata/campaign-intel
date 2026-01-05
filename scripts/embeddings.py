"""
Embedding utilities - supports both local (BGE-M3) and OpenAI embeddings.

For production (Railway), use OpenAI embeddings (fast API call).
For local dev with GPU, can use local BGE-M3.
"""

import os
from typing import List, Optional
from functools import lru_cache

# Embedding dimensions by model
EMBEDDING_DIMENSIONS = {
    "BAAI/bge-m3": 1024,
    "text-embedding-3-small": 1024,  # We request 1024 dims for consistency
    "text-embedding-3-large": 1024,
}

# Default to OpenAI in production (fast), local for dev
USE_OPENAI_EMBEDDINGS = os.getenv("USE_OPENAI_EMBEDDINGS", "true").lower() == "true"


class OpenAIEmbedder:
    """OpenAI embeddings via API - fast for production."""

    def __init__(self, model: str = "text-embedding-3-small", dimensions: int = 1024):
        import os
        from pathlib import Path
        from dotenv import load_dotenv
        from openai import OpenAI

        # Ensure we load the correct API key from .env
        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(env_path, override=True)

        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    def encode(
        self,
        texts: List[str],
        batch_size: int = 100,
        show_progress_bar: bool = False,
    ) -> List[List[float]]:
        """Embed texts using OpenAI API. Returns list of embedding vectors."""
        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
            )

            # Sort by index to maintain order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            batch_embeddings = [item.embedding for item in sorted_data]
            all_embeddings.extend(batch_embeddings)

            if show_progress_bar:
                print(f"Embedded {min(i + batch_size, len(texts))}/{len(texts)}")

        return all_embeddings


class LocalEmbedder:
    """Local sentence-transformer embeddings - for dev with GPU."""

    def __init__(self, model: str = "BAAI/bge-m3"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model)
        self.model_name = model

    def encode(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ) -> List[List[float]]:
        """Embed texts using local model. Returns list of embedding vectors."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
        )
        return embeddings.tolist()


@lru_cache(maxsize=1)
def get_embedder(use_openai: Optional[bool] = None):
    """
    Get the appropriate embedder based on config.

    Args:
        use_openai: Override config. If None, uses USE_OPENAI_EMBEDDINGS env var.

    Returns:
        Embedder instance (OpenAI or Local)
    """
    if use_openai is None:
        use_openai = USE_OPENAI_EMBEDDINGS

    if use_openai:
        print("Using OpenAI embeddings (API)")
        return OpenAIEmbedder()
    else:
        print("Using local BGE-M3 embeddings")
        return LocalEmbedder()


def embed_query(query: str, use_openai: Optional[bool] = None) -> List[float]:
    """Embed a single query string."""
    embedder = get_embedder(use_openai)
    embeddings = embedder.encode([query])
    return embeddings[0]


def embed_texts(texts: List[str], use_openai: Optional[bool] = None, show_progress: bool = False) -> List[List[float]]:
    """Embed multiple texts."""
    embedder = get_embedder(use_openai)
    return embedder.encode(texts, show_progress_bar=show_progress)


if __name__ == "__main__":
    # Quick test
    test_texts = [
        "Ohio voters on economy",
        "What did voters say about healthcare?",
    ]

    print("Testing OpenAI embeddings...")
    embeddings = embed_texts(test_texts, use_openai=True)
    print(f"Got {len(embeddings)} embeddings, dim={len(embeddings[0])}")

    print("\nTesting single query...")
    emb = embed_query("union workers in Pennsylvania", use_openai=True)
    print(f"Query embedding dim={len(emb)}")
