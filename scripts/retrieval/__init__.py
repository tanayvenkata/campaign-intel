"""
Retrieval package for focus groups and strategy memos.

This package provides:
- SharedResources: Singleton for expensive resources (embedding model, Pinecone index)
- LLMRouter: Query routing to relevant content
- FocusGroupRetrieverV2: Focus group transcript retrieval
- StrategyMemoRetriever: Strategy memo retrieval
- Data classes: RetrievalResult, GroupedResults, StrategyRetrievalResult, etc.

Example usage:
    from scripts.retrieval import FocusGroupRetrieverV2, LLMRouter

    retriever = FocusGroupRetrieverV2(use_router=True)
    results = retriever.retrieve("What did voters say about the economy?")
"""

# Re-export types
from scripts.retrieval.types import (
    RetrievalResult,
    GroupedResults,
    StrategyRetrievalResult,
    StrategyGroupedResults,
    RouterResult,
)

# Re-export shared resources
from scripts.retrieval.base import (
    SharedResources,
    BaseRetriever,
    INDEX_NAME,
    DIMENSION,
)

# Re-export router
from scripts.retrieval.router import LLMRouter

# For backward compatibility, also import from the original module
# This allows existing code to keep working while we migrate
from scripts.retrieve import (
    FocusGroupRetrieverV2,
    StrategyMemoRetriever,
    format_results_for_display,
    format_strategy_results,
)

# Hybrid retrieval (BM25 + dense fusion) - lazy import to avoid rank_bm25 dependency in prod
try:
    from scripts.retrieval.bm25 import BM25Retriever, BM25Result
    from scripts.retrieval.hybrid import HybridFocusGroupRetriever, HybridResult, FusionStrategy
    _HYBRID_AVAILABLE = True
except ImportError:
    BM25Retriever = None
    BM25Result = None
    HybridFocusGroupRetriever = None
    HybridResult = None
    FusionStrategy = None
    _HYBRID_AVAILABLE = False

__all__ = [
    # Types
    "RetrievalResult",
    "GroupedResults",
    "StrategyRetrievalResult",
    "StrategyGroupedResults",
    "RouterResult",
    # Base
    "SharedResources",
    "BaseRetriever",
    "INDEX_NAME",
    "DIMENSION",
    # Router
    "LLMRouter",
    # Retrievers
    "FocusGroupRetrieverV2",
    "StrategyMemoRetriever",
    "BM25Retriever",
    "HybridFocusGroupRetriever",
    # Result types
    "BM25Result",
    "HybridResult",
    "FusionStrategy",
    # Formatters
    "format_results_for_display",
    "format_strategy_results",
]
