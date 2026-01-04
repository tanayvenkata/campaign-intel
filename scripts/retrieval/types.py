"""
Data classes for retrieval results.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class RetrievalResult:
    """Single retrieval result."""
    chunk_id: str
    score: float
    content: str
    content_original: str
    focus_group_id: str
    participant: str
    participant_profile: str
    section: str
    source_file: str
    line_number: int
    preceding_moderator_q: str = ""


@dataclass
class GroupedResults:
    """Results grouped by focus group with metadata."""
    focus_group_id: str
    focus_group_metadata: Dict
    chunks: List[RetrievalResult]


@dataclass
class StrategyRetrievalResult:
    """Single strategy memo retrieval result."""
    chunk_id: str
    score: float
    content: str
    race_id: str
    section: str
    subsection: str
    outcome: str
    state: str
    year: int
    margin: float
    source_file: str
    line_number: int


@dataclass
class StrategyGroupedResults:
    """Results grouped by race with metadata."""
    race_id: str
    race_metadata: Dict
    chunks: List[StrategyRetrievalResult]


@dataclass
class RouterResult:
    """Result from unified content router."""
    content_type: str  # "quotes", "lessons", or "both"
    focus_group_ids: Optional[List[str]]  # None means search all FGs
    race_ids: Optional[List[str]] = None  # None means search all races
    outcome_filter: Optional[str] = None  # "win", "loss", or None
    reasoning: Optional[str] = None  # Optional reasoning for debugging
