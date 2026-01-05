"""
Shared base class and resources for retrievers.
Implements singleton pattern for expensive resources (embedding model, Pinecone index).
"""

import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.config import (
    PINECONE_API_KEY,
    EMBEDDING_MODEL_LOCAL,
    RERANKER_MODEL,
)

# Index configuration
INDEX_NAME = "focus-group-v3"
MODEL_DIMENSIONS = {
    "BAAI/bge-m3": 1024,
    "intfloat/e5-base-v2": 768,
    "BAAI/bge-base-en-v1.5": 768,
    "text-embedding-3-small": 1024,
}
DIMENSION = MODEL_DIMENSIONS.get(EMBEDDING_MODEL_LOCAL, 1024)

# OpenAI embeddings config - use API in production for speed
USE_OPENAI_EMBEDDINGS = os.getenv("USE_OPENAI_EMBEDDINGS", "true").lower() == "true"
PINECONE_NAMESPACE = "openai" if USE_OPENAI_EMBEDDINGS else ""  # Empty = default namespace


class SharedResources:
    """
    Singleton manager for expensive resources.
    Loads embedding model and Pinecone index once, shared across all retrievers.
    """
    _embedding_model = None
    _reranker_model = None
    _pinecone_client = None
    _pinecone_index = None

    @classmethod
    def get_embedding_model(cls):
        """Get or create shared embedding model (OpenAI or local)."""
        if cls._embedding_model is None:
            if USE_OPENAI_EMBEDDINGS:
                from scripts.embeddings import OpenAIEmbedder
                print("Loading embedding model: OpenAI text-embedding-3-small (API)")
                cls._embedding_model = OpenAIEmbedder(dimensions=1024)
            else:
                from sentence_transformers import SentenceTransformer
                print(f"Loading embedding model: {EMBEDDING_MODEL_LOCAL}")
                cls._embedding_model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
        return cls._embedding_model

    @classmethod
    def get_reranker_model(cls):
        """Get or create shared reranker (wrapper with .rerank() method)."""
        if cls._reranker_model is None:
            from scripts.rerank import Reranker
            print(f"Loading reranker model: {RERANKER_MODEL}")
            cls._reranker_model = Reranker(model_name=RERANKER_MODEL)
        return cls._reranker_model

    @classmethod
    def get_pinecone_index(cls):
        """Get or create shared Pinecone index connection."""
        if cls._pinecone_index is None:
            from pinecone import Pinecone
            cls._pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
            cls._pinecone_index = cls._pinecone_client.Index(INDEX_NAME)
        return cls._pinecone_index

    @classmethod
    def reset(cls):
        """Reset all shared resources (useful for testing)."""
        cls._embedding_model = None
        cls._reranker_model = None
        cls._pinecone_client = None
        cls._pinecone_index = None


class BaseRetriever:
    """
    Base class for all retrievers.
    Provides shared access to embedding model and Pinecone index.
    """

    def __init__(self, use_reranker: bool = True, verbose: bool = False):
        self.use_reranker = use_reranker
        self.verbose = verbose

        # Use shared resources
        self.model = SharedResources.get_embedding_model()
        self.index = SharedResources.get_pinecone_index()

        if use_reranker:
            self.reranker = SharedResources.get_reranker_model()
        else:
            self.reranker = None

    def embed_query(self, query: str):
        """Embed a query using the shared model (OpenAI or local)."""
        if USE_OPENAI_EMBEDDINGS:
            # OpenAI embedder returns list of embeddings for list of texts
            embeddings = self.model.encode([query])
            return embeddings[0]
        else:
            # SentenceTransformer returns numpy array for single text
            return self.model.encode(query).tolist()

    def log(self, message: str):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
