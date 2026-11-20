"""SecondSelf: Your Personal AI Second Brain (The Oracle - Task 4.2).

Unified Streamlit Web Application combining:
1. 🔮 Ask Your Brain: Grounded RAG conversational Q&A with live token streaming and citations
2. 🕸️ Living Brain: Interactive force-directed Vis-Network knowledge graph
3. 📥 Quick Ingestion: Capture text, URLs, and files directly with instant classification
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# Ensure root directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.capture import capture, list_raw_captures
from src.classify import classify_all, get_groq_client, get_best_model
from src.link import auto_link_wiki, get_embedding_model, DEFAULT_CACHE_FILE, DEFAULT_WIKI_DIR
from src.build_graph import build_and_export, render_graph_html, DEFAULT_OUTPUT_FILE
from src.ask import ask_stream, retrieve_relevant_notes

# Load environment variables
load_dotenv()

# Page Configuration
st.set_page_config(
    page_title="SecondSelf — Your Personal AI Second Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    /* Dark aesthetic overrides */
    .stApp {
        background-color: #0E1117;
    }
    
    /* Header branding */
    .brain-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
    }
    .brain-title {
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #F8FAFC;
    }
    .brain-tagline {
        font-size: 14px;
        color: #94A3B8;
    }
    
    /* Metric pill cards */
    .metric-card {
        background: #1E293B;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .metric-val {
        font-size: 22px;
        font-weight: 700;
        color: #F8FAFC;
    }
    .metric-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        color: #94A3B8;
        letter-spacing: 0.5px;
    }
    
    /* PARA Badges */
    .badge-projects { background: #EF4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-areas { background: #3B82F6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-resources { background: #10B981; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-archives { background: #6B7280; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    
    /* Source citation pill */
    .citation-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 10px;
        margin-top: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Loading embedding model...")
def get_cached_embedder():
    """Load SentenceTransformer once for the process."""
    return get_embedding_model()


@st.cache_data
def get_graph_html_content() -> str:
    """Read or generate graph.html."""
    html_file = Path("graph.html")
    if not html_file.exists():
        build_and_export()
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<p style='color:white;text-align:center;'>Knowledge Graph not yet compiled.</p>"


@st.cache_data
def get_vault_statistics() -> Dict[str, Any]:
    """Calculate vault note counts, connections, and category distribution."""
    graph_file = Path("graph.json")
    if not graph_file.exists():
        build_and_export()

    try:
        data = json.loads(graph_file.read_text(encoding="utf-8"))
        stats = data.get("stats", {})
        return {
            "total_notes": stats.get("total_nodes", 0),
            "total_edges": stats.get("total_edges", 0),
            "categories": stats.get("categories", {}),
        }
    except Exception:
        return {"total_notes": 0, "total_edges": 0, "categories": {}}


# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "👋 Welcome to **SecondSelf**, your autonomous personal AI second brain!\n\nAsk me anything in plain English about your notes, frameworks, architecture decisions, or ideas, and I will synthesize an answer grounded strictly in your personal vault with `[[citations]]`.",
            "sources": [],
        }
    ]

# Pre-load embedding model in background
get_cached_embedder()


# =========================================================================
# SIDEBAR
# =========================================================================
with st.sidebar:
    st.markdown(
        """
        <div class="brain-header">
            <span style="font-size:32px;">🧠</span>
            <div>
                <div class="brain-title">SecondSelf</div>
                <div class="brain-tagline">AI Second Brain</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stats = get_vault_statistics()
    st.markdown("### 📊 Vault Statistics")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-val">{stats['total_notes']}</div>
                <div class="metric-label">Notes</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-val">{stats['total_edges']}</div>
                <div class="metric-label">Semantic Links</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Category pills
    cats = stats.get("categories", {})
    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 16px 0;">
            <span class="badge-projects">Projects: {cats.get('Projects', 0)}</span>
            <span class="badge-areas">Areas: {cats.get('Areas', 0)}</span>
            <span class="badge-resources">Resources: {cats.get('Resources', 0)}</span>
            <span class="badge-archives">Archives: {cats.get('Archives', 0)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # One-Click Re-index Action
    st.markdown("### ⚡ Vault Maintenance")
    if st.button("🔄 Sync & Re-index Brain", use_container_width=True, type="primary"):
        with st.status("Re-indexing Second Brain...", expanded=True) as status:
            st.write("1. Classifying unorganized raw items...")
            classify_all()
            st.write("2. Computing embeddings and semantic auto-links...")
            auto_link_wiki()
            st.write("3. Compiling knowledge graph canvas...")
            build_and_export()
            status.update(label="Second Brain Synced & Re-indexed!", state="complete", expanded=False)
        st.cache_data.clear()
        st.rerun()

    # API Status
    st.markdown("---")
    api_key = os.getenv("GROQ_API_KEY") or (st.secrets.get("GROQ_API_KEY") if hasattr(st, "secrets") else None)
    if api_key:
        st.success("🟢 Groq API Connected", icon="✅")
    else:
        st.warning("⚠️ Missing GROQ_API_KEY. Add it to .env or Streamlit Secrets.")

    st.markdown(
        "<div style='font-size:11px;color:#64748B;text-align:center;margin-top:20px;'>"
        "SecondSelf v1.0 • Built with Streamlit, Groq & SentenceTransformers"
        "</div>",
        unsafe_allow_html=True,
    )


# =========================================================================
# MAIN CONTENT TABS
# =========================================================================
tab_ask, tab_graph, tab_capture = st.tabs([
    "🔮 Ask Your Brain",
    "🕸️ Living Brain (Visual Graph)",
    "📥 Ingest Knowledge",
])

# -------------------------------------------------------------------------
# TAB 1: ASK YOUR BRAIN (RAG CHAT)
# -------------------------------------------------------------------------
with tab_ask:
    st.markdown("### 💬 Ask Your Second Brain")
    st.caption("Ask questions in plain English. Answers are synthesized exclusively from your accumulated notes with exact citations.")

    # Starter question buttons
    col_q1, col_q2, col_q3, col_q4 = st.columns(4)
    starter_query = None
    with col_q1:
        if st.button("📌 What is the PARA framework?", use_container_width=True):
            starter_query = "What is the PARA framework and what are its four categories?"
    with col_q2:
        if st.button("🚀 FastAPI best practices?", use_container_width=True):
            starter_query = "What are the recommended production architecture principles for FastAPI?"
    with col_q3:
        if st.button("🧘 Deep work & focus habits?", use_container_width=True):
            starter_query = "What are the deep work habits and attention management practices?"
    with col_q4:
        if st.button("📜 Vannevar Bush's Memex?", use_container_width=True):
            starter_query = "What is the historical concept of the Memex?"

    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"📚 Grounded Sources ({len(msg['sources'])})", expanded=False):
                    for s in msg["sources"]:
                        badge_class = f"badge-{s.category.lower()}" if s.category.lower() in ["projects", "areas", "resources", "archives"] else "badge-resources"
                        st.markdown(
                            f"""
                            <div class="citation-card">
                                <div><strong>[[{s.title}]]</strong> <span class="{badge_class}">{s.category}</span> <span style="color:#94A3B8;font-size:12px;">(Similarity: {s.similarity * 100:.1f}%)</span></div>
                                <div style="color:#CBD5E1;font-size:12px;margin-top:4px;">{s.summary}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    # Chat Input Handling
    user_prompt = st.chat_input("Ask anything from your Second Brain...")
    active_query = user_prompt or starter_query

    if active_query:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": active_query, "sources": []})
        with st.chat_message("user"):
            st.markdown(active_query)

        # Generate Assistant Response
        with st.chat_message("assistant"):
            try:
                stream_gen, sources, model_name = ask_stream(active_query)
                response_text = st.write_stream(stream_gen)

                if sources:
                    with st.expander(f"📚 Grounded Sources ({len(sources)})", expanded=True):
                        for s in sources:
                            badge_class = f"badge-{s.category.lower()}" if s.category.lower() in ["projects", "areas", "resources", "archives"] else "badge-resources"
                            st.markdown(
                                f"""
                                <div class="citation-card">
                                    <div><strong>[[{s.title}]]</strong> <span class="{badge_class}">{s.category}</span> <span style="color:#94A3B8;font-size:12px;">(Similarity: {s.similarity * 100:.1f}%)</span></div>
                                    <div style="color:#CBD5E1;font-size:12px;margin-top:4px;">{s.summary}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "sources": sources,
                })
            except Exception as e:
                err_msg = f"Error generating answer: {e}"
                st.error(err_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": err_msg,
                    "sources": [],
                })


# -------------------------------------------------------------------------
# TAB 2: LIVING BRAIN (INTERACTIVE GRAPH)
# -------------------------------------------------------------------------
with tab_graph:
    st.markdown("### 🕸️ Interactive Knowledge Brain")
    st.caption("A live force-directed map of your personal wiki. Nodes pulse and scale with connectivity; edges represent dense semantic vector similarities. Hover to inspect summaries or click to open full details.")

    graph_html = get_graph_html_content()
    components.html(graph_html, height=760, scrolling=False)


# -------------------------------------------------------------------------
# TAB 3: INGEST KNOWLEDGE
# -------------------------------------------------------------------------
with tab_capture:
    st.markdown("### 📥 Capture Anything to Your Second Brain")
    st.caption("Drop thoughts, web links, or documents into your second brain. Our pipeline automatically organizes them using the PARA framework and discovers semantic links.")

    ingest_type = st.radio("Capture Type", ["Quick Note", "Web Article URL", "Upload Document (.pdf, .txt, .md)"], horizontal=True)

    with st.form("capture_form", clear_on_submit=True):
        note_title = st.text_input("Title (Optional)", placeholder="Give this capture an intuitive title...")
        note_tags = st.text_input("Tags (Optional, comma-separated)", placeholder="e.g. ai, python, ideas")

        captured_text = None
        captured_url = None
        captured_file_path = None

        if ingest_type == "Quick Note":
            captured_text = st.text_area("Note Content", height=150, placeholder="Type or paste your thoughts, quotes, or ideas here...")
        elif ingest_type == "Web Article URL":
            captured_url = st.text_input("URL Link", placeholder="https://example.com/article")
        else:
            uploaded_file = st.file_uploader("Choose a document", type=["txt", "md", "pdf"])
            if uploaded_file is not None:
                # Save to temporary file for parser
                temp_dir = Path(tempfile.gettempdir()) / "secondself_uploads"
                temp_dir.mkdir(exist_ok=True)
                temp_file = temp_dir / uploaded_file.name
                temp_file.write_bytes(uploaded_file.getbuffer())
                captured_file_path = str(temp_file)

        auto_process = st.checkbox("⚡ Auto-classify and link into wiki immediately", value=True)
        submitted = st.form_submit_button("Capture Knowledge", type="primary", use_container_width=True)

        if submitted:
            parsed_tags = [t.strip() for t in note_tags.split(",") if t.strip()] if note_tags else []
            try:
                if ingest_type == "Quick Note" and not captured_text:
                    st.error("Please enter some text content.")
                elif ingest_type == "Web Article URL" and not captured_url:
                    st.error("Please enter a valid URL.")
                elif ingest_type == "Upload Document (.pdf, .txt, .md)" and not captured_file_path:
                    st.error("Please select a file to upload.")
                else:
                    with st.spinner("Ingesting into raw vault..."):
                        rec = capture(
                            text=captured_text,
                            url=captured_url,
                            file_path=captured_file_path,
                            title=note_title or None,
                            tags=parsed_tags,
                        )

                    st.success(f"Captured successfully! (ID: {rec.id})")

                    if auto_process:
                        with st.spinner("Classifying and auto-linking into wiki..."):
                            raw_file = Path("raw") / f"{rec.id}.json"
                            from src.classify import process_capture_file
                            process_capture_file(raw_file)
                            auto_link_wiki()
                            build_and_export()
                            st.cache_data.clear()
                        st.success("Organized with PARA and semantic links updated!")
                        st.rerun()

            except Exception as e:
                st.error(f"Ingestion failed: {e}")
