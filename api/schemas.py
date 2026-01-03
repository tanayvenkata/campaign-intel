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
    score_threshold: float = 0.75

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
