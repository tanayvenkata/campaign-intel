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
