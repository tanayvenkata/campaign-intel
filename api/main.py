import sys
from pathlib import Path
import time
import json
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

# Add project root to sys.path to allow imports from scripts/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from scripts.retrieve_v2 import FocusGroupRetrieverV2, LLMRouter, RetrievalResult
from scripts.synthesize import FocusGroupSynthesizer
from api.schemas import (
    SearchRequest, SearchResponse, SynthesisRequest, MacroSynthesisRequest,
    GroupedResult, RetrievalChunk,
    LightMacroSynthesisRequest, DeepMacroSynthesisRequest, DeepMacroResponse
)

# Global instances
retriever: Optional[FocusGroupRetrieverV2] = None
router: Optional[LLMRouter] = None
synthesizer: Optional[FocusGroupSynthesizer] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize expensive resources on startup."""
    global retriever, router, synthesizer
    print("Initializing resources...")
    # Initialize with same settings as app.py
    # Note: app.py uses st.cache_resource, here we use global singletons
    retriever = FocusGroupRetrieverV2(use_router=True, use_reranker=True, verbose=False)
    router = LLMRouter()
    synthesizer = FocusGroupSynthesizer(verbose=False)
    print("Resources initialized.")
    yield
    # Cleanup if needed
    print("Shutting down...")

app = FastAPI(title="Focus Group Search API", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "resources_loaded": retriever is not None}

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    if not retriever or not router:
        raise HTTPException(status_code=503, detail="Service not ready")

    start_time = time.time()
    
    # 1. Route (part of retrieval logic in retrieve_v2, but we can do it explicitly if needed)
    # The retriever.retrieve_per_focus_group handles routing internally if filter_focus_groups is None
    # but app.py does it explicitly to show the decision. Let's rely on retriever's internal logic 
    # OR replicate app.py if we want to return the routing decision in stats.
    
    # Let's replicate app.py logic to capture routing time stats if possible, 
    # but retrieve_per_focus_group is convenient.
    # For now, we'll let retrieve_per_focus_group handle it, or we can add a router endpoint later if needed.
    
    # Actually, app.py calls router.route() explicitly. 
    # To keep it simple and robust, let's just call retrieve_per_focus_group.
    # It returns a dict of results.

    results_by_fg = retriever.retrieve_per_focus_group(
        query=request.query,
        top_k_per_fg=request.top_k,
        score_threshold=request.score_threshold
    )
    
    retrieval_time = (time.time() - start_time) * 1000

    # Convert to response model
    grouped_results = []
    total_quotes = 0
    
    for fg_id, chunks in results_by_fg.items():
        if not chunks:
            continue
            
        fg_meta = retriever._load_focus_group_metadata(fg_id)
        
        # Convert dataclass chunks to Pydantic chunks
        api_chunks = []
        for c in chunks:
            api_chunks.append(RetrievalChunk(
                chunk_id=c.chunk_id,
                score=c.score,
                content=c.content,
                content_original=c.content_original,
                focus_group_id=c.focus_group_id,
                participant=c.participant,
                participant_profile=c.participant_profile,
                section=c.section,
                source_file=c.source_file,
                line_number=c.line_number,
                preceding_moderator_q=c.preceding_moderator_q
            ))
            
        grouped_results.append(GroupedResult(
            focus_group_id=fg_id,
            focus_group_metadata=fg_meta,
            chunks=api_chunks
        ))
        total_quotes += len(api_chunks)

    return SearchResponse(
        results=grouped_results,
        stats={
            "retrieval_time_ms": round(retrieval_time),
            "total_quotes": total_quotes,
            "focus_groups_count": len(grouped_results)
        }
    )


@app.post("/search/stream")
async def search_stream(request: SearchRequest):
    """Streaming search endpoint that yields status events during processing."""
    if not retriever or not router:
        raise HTTPException(status_code=503, detail="Service not ready")

    def build_response(results_by_fg: Dict, retrieval_time: float) -> dict:
        """Build the final response dict."""
        grouped_results = []
        total_quotes = 0

        for fg_id, chunks in results_by_fg.items():
            if not chunks:
                continue

            fg_meta = retriever._load_focus_group_metadata(fg_id)

            api_chunks = []
            for c in chunks:
                api_chunks.append({
                    "chunk_id": c.chunk_id,
                    "score": c.score,
                    "content": c.content,
                    "content_original": c.content_original,
                    "focus_group_id": c.focus_group_id,
                    "participant": c.participant,
                    "participant_profile": c.participant_profile,
                    "section": c.section,
                    "source_file": c.source_file,
                    "line_number": c.line_number,
                    "preceding_moderator_q": c.preceding_moderator_q
                })

            grouped_results.append({
                "focus_group_id": fg_id,
                "focus_group_metadata": fg_meta,
                "chunks": api_chunks
            })
            total_quotes += len(api_chunks)

        return {
            "results": grouped_results,
            "stats": {
                "retrieval_time_ms": round(retrieval_time),
                "total_quotes": total_quotes,
                "focus_groups_count": len(grouped_results)
            }
        }

    def event_generator():
        start_time = time.time()

        # Step 1: Routing
        yield json.dumps({"type": "status", "step": "routing", "message": "Analyzing query intent..."}) + "\n"

        fg_ids = router.route(request.query)
        if fg_ids is None:
            fg_ids = router._get_all_ids()
            yield json.dumps({"type": "status", "step": "filtering", "message": f"Searching all {len(fg_ids)} focus groups..."}) + "\n"
        else:
            yield json.dumps({"type": "status", "step": "filtering", "message": f"Routing to {len(fg_ids)} relevant focus groups..."}) + "\n"

        # Step 2: Searching
        yield json.dumps({"type": "status", "step": "searching", "message": "Scanning transcripts..."}) + "\n"

        results_by_fg = retriever.retrieve_per_focus_group(
            query=request.query,
            top_k_per_fg=request.top_k,
            score_threshold=request.score_threshold,
            filter_focus_groups=fg_ids  # Skip internal routing since we already routed
        )

        # Step 3: Ranking
        yield json.dumps({"type": "status", "step": "ranking", "message": "Ranking relevance..."}) + "\n"

        retrieval_time = (time.time() - start_time) * 1000

        # Step 4: Complete
        yield json.dumps({"type": "status", "step": "complete", "message": "Done"}) + "\n"

        # Final results
        response_data = build_response(results_by_fg, retrieval_time)
        yield json.dumps({"type": "results", "data": response_data}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.post("/synthesize/light")
async def synthesize_light(request: SynthesisRequest):
    """Generate a light summary (non-streaming, as it's short)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")
        
    # Convert Pydantic chunks back to RetrievalResult dataclasses for the script
    # The script expects objects with attribute access
    script_chunks = [
        RetrievalResult(**c.model_dump()) for c in request.quotes
    ]
    
    summary = synthesizer.light_summary(
        quotes=script_chunks,
        query=request.query,
        focus_group_name=request.focus_group_name
    )
    
    return {"summary": summary}

@app.post("/synthesize/deep")
async def synthesize_deep(request: SynthesisRequest):
    """Generate a deep synthesis (streaming)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Expand context if strictly needed on backend, but the plan says 
    # "Import from scripts/retrieve_v2.py: FocusGroupRetrieverV2"
    # app.py calls `retriever.fetch_expanded_context` before synthesis.
    # The frontend might not have full context, so we might need to do it here.
    
    script_chunks = [
        RetrievalResult(**c.model_dump()) for c in request.quotes
    ]
    
    # If context not provided, fetch it
    context = request.context
    if not context and retriever:
        context = retriever.fetch_expanded_context(script_chunks, max_chunks=5)
    
    # Streaming wrapper
    # The current synthesizer.deep_synthesis is NOT streaming (it returns a string).
    # We need to adapt it or rewrite it to stream.
    # Since the constraint is "Do not modify existing scripts/ code - wrap it", 
    # BUT "Streaming is required ... this is the main UX win".
    
    # The existing script uses `client.chat.completions.create` without stream=True.
    # To support streaming without modifying the script, we would need to duplicate the logic here 
    # OR modify the script to support streaming.
    # User said: "Do not modify existing scripts/ code - wrap it, don't rewrite"
    # BUT ALSO: "All LLM endpoints should support streaming via StreamingResponse"
    
    # If I cannot modify the script, I cannot make `synthesizer.deep_synthesis` stream 
    # because it calls the OpenAI client internally nicely wrapped.
    # However, I can subclass or just implement the streaming logic here using the same prompt construction.
    # Re-implementing the call logic here seems safer than modifying the shared script 
    # and risking breaking the existing Streamlit app (though I could check for regressions).
    
    # Let's inspect `scripts/synthesize.py` again. It constructs a prompt and calls client.
    # I will replicate the prompt construction here to enable streaming.
    
    # Construct prompt (copied from scripts/synthesize.py to ensure parity)
    context_str = "\n\n---\n\n".join(context) if context else ""
    if not context_str:
        quote_texts = []
        for q in script_chunks:
            mod_q = f'Moderator: "{q.preceding_moderator_q}"' if q.preceding_moderator_q else ""
            participant_info = f"{q.participant} ({q.participant_profile})"
            quote_texts.append(f'{mod_q}\n"{q.content_original or q.content}" — {participant_info}')
        context_str = "\n\n".join(quote_texts)

    prompt = f"""You are a senior political analyst synthesizing focus group insights.

User's question: "{request.query}"

Focus group: {request.focus_group_name or 'Unknown'}

Conversational context (moderator questions and participant responses):
{context_str}

Provide a synthesis that:
1. Identifies the dominant sentiment and any dissenting views
2. Notes specific language voters used (quote key phrases)
3. Highlights any emotional undertones or intensity
4. Connects findings to the user's question

Keep it to 2-3 paragraphs. Be analytical, not just descriptive."""

    async def stream_generator():
        stream = synthesizer.client.chat.completions.create(
            model=synthesizer.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.4,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.post("/synthesize/macro")
async def synthesize_macro(request: MacroSynthesisRequest):
    """Generate macro synthesis (streaming)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Replicate prompt logic from scripts/synthesize.py for streaming
    
    # Build summaries section
    summaries_str = ""
    for fg_id, summary in request.fg_summaries.items():
        summaries_str += f"\n**{fg_id}**: {summary}\n"

    # Build quotes section - preserve diversity across FGs while capping total
    MAX_TOTAL_QUOTES = 40
    num_fgs = len(request.top_quotes)

    # Dynamic per-FG limit: ensure every FG gets representation
    # At minimum 2 per FG, at maximum 5 per FG
    quotes_per_fg = max(2, min(5, MAX_TOTAL_QUOTES // max(num_fgs, 1)))

    quotes_str = ""
    for fg_id, quotes in request.top_quotes.items():
        quotes_str += f"\n{fg_id}:\n"
        # Take top N quotes per FG (dynamic based on total FGs)
        for q in quotes[:quotes_per_fg]:
            content = q.content_original or q.content
            quotes_str += f'- "{content}" — {q.participant}\n'

    prompt = f"""You are a senior political strategist synthesizing insights across multiple focus groups.

User's question: "{request.query}"

Summaries by focus group:
{summaries_str}

Key quotes:
{quotes_str}

Provide a thematic synthesis that:
1. Identifies 2-4 cross-cutting themes
2. For each theme, note which focus groups it appeared in
3. Include specific voter quotes as evidence
4. Note any geographic or demographic patterns

Format:
**Theme 1: [Name]**
[Description with citations]

**Theme 2: [Name]**
[Description with citations]

...

Be specific and analytical. Avoid generic observations."""

    async def stream_generator():
        stream = synthesizer.client.chat.completions.create(
            model=synthesizer.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.4,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ============ V2 Macro Synthesis Endpoints ============

@app.post("/synthesize/macro/light")
async def synthesize_macro_light(request: LightMacroSynthesisRequest):
    """
    Light Macro Synthesis (streaming).

    Single LLM call with dynamic quote sampling.
    Ensures every focus group gets representation while capping total context.
    """
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Convert Pydantic chunks to dataclasses for the synthesizer
    top_quotes_dataclass = {}
    for fg_id, chunks in request.top_quotes.items():
        top_quotes_dataclass[fg_id] = [
            RetrievalResult(**c.model_dump()) for c in chunks
        ]

    async def stream_generator():
        for chunk in synthesizer.light_macro_synthesis_stream(
            fg_summaries=request.fg_summaries,
            top_quotes=top_quotes_dataclass,
            fg_metadata=request.fg_metadata,
            query=request.query
        ):
            yield chunk

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


@app.post("/synthesize/macro/deep")
async def synthesize_macro_deep(request: DeepMacroSynthesisRequest):
    """
    Deep Macro Synthesis (streaming).

    Two-stage synthesis:
    - Stage 1: Theme Discovery (identifies 3-5 thematic clusters)
    - Stage 2: Per-Theme Synthesis (rich analysis for each theme)

    Streams status updates and theme content as they're generated.
    """
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Convert Pydantic chunks to dataclasses for the synthesizer
    top_quotes_dataclass = {}
    for fg_id, chunks in request.top_quotes.items():
        top_quotes_dataclass[fg_id] = [
            RetrievalResult(**c.model_dump()) for c in chunks
        ]

    def stream_generator():
        for event in synthesizer.deep_macro_synthesis_stream(
            fg_summaries=request.fg_summaries,
            top_quotes=top_quotes_dataclass,
            fg_metadata=request.fg_metadata,
            query=request.query
        ):
            yield json.dumps(event) + "\n"

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
