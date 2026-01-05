from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class RetrievalChunk(BaseModel):
    """Mirror of RetrievalResult dataclass."""
    chunk_id: str
    score: float
    content: str
    content_original: Optional[str] = None
    focus_group_id: str
    participant: str
    participant_profile: str
    section: str
    source_file: str
    line_number: int
    preceding_moderator_q: Optional[str] = ""

class GroupedResult(BaseModel):
    """Mirror of GroupedResults dataclass."""
    focus_group_id: str
    focus_group_metadata: Dict[str, Any]
    chunks: List[RetrievalChunk]

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    score_threshold: float = 0.50  # Lowered for OpenAI embeddings (which produce ~0.55-0.65 scores)

class SearchResponse(BaseModel):
    results: List[GroupedResult]
    stats: Dict[str, Any]

class SynthesisRequest(BaseModel):
    quotes: List[RetrievalChunk]
    query: str
    context: Optional[List[str]] = None
    focus_group_name: Optional[str] = ""

class MacroSynthesisRequest(BaseModel):
    fg_summaries: Dict[str, str]
    top_quotes: Dict[str, List[RetrievalChunk]]
    query: str


# V2 Macro Synthesis schemas (with metadata support)

class FocusGroupMetadata(BaseModel):
    """Metadata for a focus group."""
    location: Optional[str] = "Unknown"
    race_name: Optional[str] = "Unknown race"
    outcome: Optional[str] = "unknown"
    # Additional fields as needed
    participant_summary: Optional[str] = None
    key_themes: Optional[List[str]] = None


class LightMacroSynthesisRequest(BaseModel):
    """Request for Light Macro Synthesis - single LLM call with dynamic quote sampling."""
    fg_summaries: Dict[str, str]
    top_quotes: Dict[str, List[RetrievalChunk]]
    fg_metadata: Dict[str, Dict[str, Any]]  # fg_id -> metadata dict
    query: str


class DeepMacroSynthesisRequest(BaseModel):
    """Request for Deep Macro Synthesis - two-stage theme discovery + per-theme synthesis."""
    fg_summaries: Dict[str, str]
    top_quotes: Dict[str, List[RetrievalChunk]]
    fg_metadata: Dict[str, Dict[str, Any]]  # fg_id -> metadata dict
    query: str


class DeepMacroTheme(BaseModel):
    """A theme discovered and synthesized in Deep Macro Synthesis."""
    name: str
    focus_group_ids: List[str]
    rationale: Optional[str] = ""
    synthesis: str


class DeepMacroResponse(BaseModel):
    """Response from Deep Macro Synthesis (non-streaming)."""
    themes: List[DeepMacroTheme]
    metadata: Dict[str, Any]  # timing, llm_calls, etc.


# ============ Strategy Memo Schemas ============

class StrategyChunk(BaseModel):
    """Mirror of StrategyRetrievalResult dataclass."""
    chunk_id: str
    score: float
    content: str
    race_id: str
    section: str
    subsection: Optional[str] = ""
    outcome: str
    state: str
    year: int
    margin: float
    source_file: str
    line_number: int


class StrategyGroupedResult(BaseModel):
    """Strategy results grouped by race."""
    race_id: str
    race_metadata: Dict[str, Any]
    chunks: List[StrategyChunk]


class UnifiedSearchResponse(BaseModel):
    """Response from unified search - includes both quotes and lessons."""
    content_type: str  # "quotes", "lessons", or "both"
    quotes: List[GroupedResult]  # Focus group results
    lessons: List[StrategyGroupedResult]  # Strategy memo results
    stats: Dict[str, Any]


# ============ Strategy Synthesis Schemas ============

class StrategySynthesisRequest(BaseModel):
    """Request for strategy synthesis (light or deep)."""
    chunks: List[StrategyChunk]
    query: str
    race_name: Optional[str] = ""


class StrategyMacroSynthesisRequest(BaseModel):
    """Request for cross-race strategy synthesis."""
    race_summaries: Dict[str, str]  # race_id -> light summary
    top_chunks: Dict[str, List[StrategyChunk]]  # race_id -> chunks
    race_metadata: Dict[str, Dict[str, Any]]  # race_id -> metadata
    query: str


class UnifiedMacroSynthesisRequest(BaseModel):
    """Request for unified macro synthesis combining FG quotes + strategy lessons."""
    # Focus group data
    fg_summaries: Dict[str, str]  # fg_id -> light summary
    fg_quotes: Dict[str, List[RetrievalChunk]]  # fg_id -> top quotes
    fg_metadata: Dict[str, Dict[str, Any]]  # fg_id -> metadata
    # Strategy data
    strategy_summaries: Dict[str, str]  # race_id -> light summary
    strategy_chunks: Dict[str, List[StrategyChunk]]  # race_id -> top chunks
    strategy_metadata: Dict[str, Dict[str, Any]]  # race_id -> metadata
    # Query
    query: str


# ============ Corpus Explorer Schemas ============

class CorpusItem(BaseModel):
    """A document in the corpus (focus group or strategy memo)."""
    id: str  # Unique ID (fg_id or race_id/doc_id)
    type: str  # "focus_group" or "strategy_memo"
    title: str
    date: Optional[str] = None
    location: Optional[str] = None
    race_name: Optional[str] = None
    outcome: Optional[str] = None
    file_path: str  # Relative to corpus root

class DocumentContent(BaseModel):
    """Content of a document."""
    content: str
    metadata: Dict[str, Any]

