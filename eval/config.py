"""
DeepEval configuration for focus group retrieval evaluation.
Loads API keys from .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (override=True to ignore system env vars)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

# API Configuration (all paid LLM calls go through OpenRouter for centralized cost tracking)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Model configuration (all configurable via .env)
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
SYNTHESIS_MODEL = os.getenv("SYNTHESIS_MODEL", "anthropic/claude-3-haiku")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "anthropic/claude-3-haiku")

# OpenAI Configuration (for embeddings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Pinecone Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "focus-group-v1")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
FOCUS_GROUPS_DIR = DATA_DIR / "focus-groups"
EVAL_DIR = PROJECT_ROOT / "eval"

# Evaluation targets (based on Rachel's requirements)
EVAL_TARGETS = {
    "faithfulness": 1.0,        # 100% - "One bad hallucination and I'm done"
    "context_relevance": 0.8,   # >0.8 - "I need to see the source"
    "recall_at_5": 0.7,         # >0.7 - Find relevant quotes
    "latency_seconds": 2.0,     # <2s - "Faster than asking Marcus"
    "hallucination_rate": 0.0,  # 0% on negative cases
}

# Ohio 2024 focus groups (demo scenario)
OHIO_2024_FOCUS_GROUPS = [
    "race-007-fg-001-cleveland-suburbs",
    "race-007-fg-002-columbus-educated",
    "race-007-fg-003-youngstown-working-class",
]

def validate_config():
    """Validate that required configuration is present."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in .env file")

    if not DATA_DIR.exists():
        raise ValueError(f"Data directory not found: {DATA_DIR}")

    print("✓ Configuration validated")
    print(f"  - OpenRouter API key: {'*' * 10}...{OPENROUTER_API_KEY[-4:]}")
    print(f"  - Model: {OPENROUTER_MODEL}")
    print(f"  - Data directory: {DATA_DIR}")

if __name__ == "__main__":
    validate_config()
