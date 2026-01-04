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
    # Formatters
    "format_results_for_display",
    "format_strategy_results",
]
