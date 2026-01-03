#!/usr/bin/env python3
"""
Streamlit UI for focus group retrieval with synthesis.
Run with: streamlit run app.py
"""

import streamlit as st
import time
import sys
from pathlib import Path
from collections import OrderedDict

sys.path.insert(0, str(Path(__file__).parent))

from scripts.retrieve_v2 import FocusGroupRetrieverV2, LLMRouter
from scripts.synthesize import FocusGroupSynthesizer

# Page config
st.set_page_config(
    page_title="Focus Group Search",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
.quote-block {
    background-color: #f8f9fa;
    border-left: 4px solid #1f77b4;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 0 8px 8px 0;
}
.quote-text {
    font-size: 1.05rem;
    font-style: italic;
    color: #1a1a1a;
    margin-bottom: 0.5rem;
}
.quote-attribution {
    font-weight: 600;
    color: #333;
}
.quote-context {
    font-size: 0.85rem;
    color: #666;
    margin-top: 0.5rem;
}
.light-summary {
    background-color: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    border-radius: 0 8px 8px 0;
    font-style: italic;
}
.synthesis-box {
    background-color: #e7f5ff;
    border: 1px solid #74c0fc;
    padding: 1rem;
    border-radius: 8px;
    margin: 1rem 0;
}
.macro-synthesis {
    background-color: #d3f9d8;
    border: 2px solid #51cf66;
    padding: 1.5rem;
    border-radius: 8px;
    margin: 1.5rem 0;
}
</style>
""", unsafe_allow_html=True)

st.title("Focus Group Search")
st.caption("V3 Retrieval + Synthesis Layer")

# Initialize components (cached)
@st.cache_resource
def load_retriever():
    return FocusGroupRetrieverV2(use_router=True, use_reranker=True, verbose=False)

@st.cache_resource
def load_router():
    return LLMRouter()

@st.cache_resource
def load_synthesizer():
    return FocusGroupSynthesizer(verbose=False)

# Sidebar settings
with st.sidebar:
    st.header("Settings")
    top_k = st.slider("Results per focus group", 1, 10, 5)
    score_threshold = st.slider("Score threshold", 0.5, 0.9, 0.75, 0.05)
    auto_summarize = st.checkbox("Auto-generate summaries", value=True)

    st.divider()
    st.caption("Summaries use Claude Haiku via OpenRouter (~$0.002/FG)")

# Main search
query = st.text_input("Search query", placeholder="What did Ohio voters say about the economy?")

if query:
    retriever = load_retriever()
    router = load_router()
    synthesizer = load_synthesizer()

    # Router decision
    with st.spinner("Routing query..."):
        start_time = time.time()
        selected_fgs = router.route(query)
        router_time = (time.time() - start_time) * 1000

    # Display router decision (collapsed by default)
    with st.expander("Router Decision", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            if selected_fgs is None:
                st.info("**All focus groups** (no specific filter detected)")
            else:
                st.success(f"**{len(selected_fgs)} focus groups selected**: {', '.join(selected_fgs)}")
        with col2:
            st.metric("Latency", f"{router_time:.0f}ms")

    # Retrieval
    with st.spinner("Searching..."):
        start_time = time.time()
        results_by_fg = retriever.retrieve_per_focus_group(
            query,
            top_k_per_fg=top_k,
            score_threshold=score_threshold,
            filter_focus_groups=selected_fgs
        )
        retrieval_time = (time.time() - start_time) * 1000

    # Generate light summaries if enabled (cached in session state to prevent re-generation on checkbox clicks)
    # Use query + result FG IDs as cache key
    cache_key = f"{query}_{','.join(sorted(results_by_fg.keys()))}"

    if "summaries_cache_key" not in st.session_state:
        st.session_state.summaries_cache_key = None
        st.session_state.summaries = {}
        st.session_state.synthesis_time = 0

    # Only regenerate if query/results changed
    if auto_summarize and results_by_fg and st.session_state.summaries_cache_key != cache_key:
        with st.spinner("Generating summaries..."):
            start_time = time.time()
            new_summaries = {}
            for fg_id, chunks in results_by_fg.items():
                if chunks:
                    fg_meta = retriever._load_focus_group_metadata(fg_id)
                    fg_name = fg_meta.get("location", fg_id)
                    new_summaries[fg_id] = synthesizer.light_summary(chunks, query, fg_name)
            st.session_state.summaries = new_summaries
            st.session_state.summaries_cache_key = cache_key
            st.session_state.synthesis_time = (time.time() - start_time) * 1000

    summaries = st.session_state.summaries if auto_summarize else {}
    synthesis_time = st.session_state.synthesis_time if auto_summarize else 0

    # Summary stats
    total_quotes = sum(len(chunks) for chunks in results_by_fg.values())
    fg_with_results = len([fg for fg, chunks in results_by_fg.items() if chunks])

    st.subheader("Results")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total quotes", total_quotes)
    col2.metric("Focus groups", fg_with_results)
    col3.metric("Retrieval", f"{retrieval_time:.0f}ms")
    if auto_summarize:
        col4.metric("Synthesis", f"{synthesis_time:.0f}ms")

    if total_quotes == 0:
        st.warning("No results found above the score threshold.")

    # Initialize session state for deep synthesis
    if "deep_synthesis" not in st.session_state:
        st.session_state.deep_synthesis = {}

    st.divider()

    # Display results grouped by focus group
    fg_list = [(fg_id, chunks) for fg_id, chunks in results_by_fg.items() if chunks]

    # Build FG options for sidebar multiselect (after results load)
    fg_options = {}
    for fg_id, chunks in fg_list:
        fg_meta = retriever._load_focus_group_metadata(fg_id)
        location = fg_meta.get("location", fg_id)
        fg_options[fg_id] = f"{location} ({len(chunks)} quotes)"

    for fg_id, chunks in fg_list:
        # Load FG metadata
        fg_meta = retriever._load_focus_group_metadata(fg_id)
        location = fg_meta.get("location", fg_id)
        race = fg_meta.get("race_name", "")
        date = fg_meta.get("date", "")

        # Focus group card (no checkbox)
        st.markdown(f"### {location} — {len(chunks)} quotes")
        st.caption(f"{race} | {date}")

        # Light summary (auto-generated)
        if fg_id in summaries:
            st.markdown(f'<div class="light-summary">{summaries[fg_id]}</div>', unsafe_allow_html=True)

        # Expandable quotes section
        with st.expander("Show quotes", expanded=False):
            # Group quotes by moderator question
            by_question = OrderedDict()
            for chunk in chunks:
                mod_q = chunk.preceding_moderator_q or "(No moderator question)"
                section = chunk.section or ""
                key = (section, mod_q)
                if key not in by_question:
                    by_question[key] = []
                by_question[key].append(chunk)

            # Display grouped by question
            for (section, mod_q), question_chunks in by_question.items():
                st.markdown(f"""
                <div style="background-color: #e8f4f8; padding: 0.5rem 1rem; margin-top: 0.5rem; border-radius: 4px;">
                    <div style="font-size: 0.8rem; color: #666;">{section}</div>
                    <div style="font-weight: 600; color: #1f77b4;">Moderator: "{mod_q}"</div>
                </div>
                """, unsafe_allow_html=True)

                for chunk in question_chunks:
                    content = chunk.content_original if chunk.content_original else chunk.content
                    participant = chunk.participant
                    profile = chunk.participant_profile
                    score = chunk.score

                    st.markdown(f"""
                    <div class="quote-block">
                        <div class="quote-text">"{content}"</div>
                        <div class="quote-attribution">— {participant} ({profile})</div>
                        <div class="quote-context">Score: {score:.3f}</div>
                    </div>
                    """, unsafe_allow_html=True)

        # Deep synthesis button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Deep Synthesis", key=f"deep_{fg_id}"):
                with st.spinner(f"Generating deep synthesis for {location}..."):
                    # Two-stage fetch: expand quotes to full Q&A blocks
                    expanded_context = retriever.fetch_expanded_context(chunks, max_chunks=5)
                    deep_result = synthesizer.deep_synthesis(
                        chunks,
                        source_context=expanded_context,
                        query=query,
                        focus_group_name=location
                    )
                    st.session_state.deep_synthesis[fg_id] = deep_result

        # Display deep synthesis if generated
        if fg_id in st.session_state.deep_synthesis:
            st.markdown(f'<div class="synthesis-box">{st.session_state.deep_synthesis[fg_id]}</div>', unsafe_allow_html=True)

        st.divider()

    # Initialize macro synthesis result in session state
    if "macro_result" not in st.session_state:
        st.session_state.macro_result = None

    # Macro synthesis section (shows result if generated)
    if st.session_state.macro_result:
        st.markdown("---")
        st.subheader("Cross-Focus-Group Synthesis")
        st.markdown(f'<div class="macro-synthesis">{st.session_state.macro_result}</div>', unsafe_allow_html=True)
        if st.button("Clear synthesis"):
            st.session_state.macro_result = None
            st.rerun()

    # Total latency
    st.divider()
    total_time = router_time + retrieval_time + synthesis_time
    st.caption(f"Total latency: {total_time:.0f}ms")

    # Sidebar: Macro Synthesis Selection (only show after results load)
    if fg_options:
        with st.sidebar:
            st.markdown("---")
            st.subheader("Macro Synthesis")

            # Select All button
            if st.button("Select All", use_container_width=True):
                for fg_id in fg_options.keys():
                    st.session_state[f"macro_cb_{fg_id}"] = True
                st.rerun()

            st.caption("Select focus groups to compare:")

            # Checkboxes for each FG
            selected_fg_ids = []
            for fg_id, label in fg_options.items():
                if st.checkbox(label, key=f"macro_cb_{fg_id}"):
                    selected_fg_ids.append(fg_id)

            # Synthesize button
            if selected_fg_ids:
                st.markdown(f"**{len(selected_fg_ids)} selected**")
                if st.button("🔬 Synthesize", type="primary", use_container_width=True):
                    with st.spinner("Generating cross-focus-group synthesis..."):
                        selected_summaries = {fg: summaries.get(fg, "") for fg in selected_fg_ids if fg in summaries}
                        selected_quotes = {fg: results_by_fg.get(fg, []) for fg in selected_fg_ids}

                        st.session_state.macro_result = synthesizer.macro_synthesis(
                            fg_summaries=selected_summaries,
                            top_quotes=selected_quotes,
                            query=query
                        )
                        st.rerun()
