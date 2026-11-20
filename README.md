# SecondSelf: Your Personal AI Second Brain

> A personal knowledge engine that captures anything, organizes itself with the PARA method, auto-links related thoughts with dense vector embeddings, renders a living visual brain, and answers questions grounded in your own notes.

---

## 🧭 Milestone Badges & Progress

- [x] **Phase 0: Scaffolding & Setup** — Directory trees, environment configs, pinned dependencies.
- [x] **Week 1: The Archivist 🏅** — Robust multi-source capture pipeline (`raw/` vault populated with 18 real captures).
- [x] **Week 2: The Librarian 🏅** — Automated PARA classification (`classify.py`) and semantic auto-linking (`link.py`).
  - [x] **Task 2.1 (The Sorting Hat):** Classified 18 captures into PARA structure with summaries and tags.
  - [x] **Task 2.2 (Connect the Dots):** 384-dim MiniLM embeddings + cosine auto-linking with `[[wikilinks]]`.
- [x] **Week 3: The Cartographer 🏅** — Interactive force-directed knowledge graph (`vis-network`).
  - [x] **Task 3.1 (Give It a Shape):** Compiled wiki notes and links into nodes/edges graph representation (`graph.json`).
  - [x] **Task 3.2 (The Brain Comes Alive):** Interactive vis-network canvas (`graph.html`) with search, PARA filters, hover tooltips, and click inspection drawer.
- [x] **Week 4: The Oracle 🏅** — Grounded RAG synthesis and public Streamlit deployment.
  - [x] **Task 4.1 (Ask Your Brain):** Natural-language retrieval-augmented Q&A engine (`ask.py`) with strict grounding and [[citations]].
  - [x] **Task 4.2 (Give It a Face):** Unified Streamlit app (`app.py`) combining knowledge graph, grounded RAG Q&A, and live capture.
  - [x] **Task 4.3 (Ship It Public):** Cloud deployment configuration for Streamlit Community Cloud.

---

## 🛠️ Project Structure

```text
Second Brain/
├── .streamlit/
│   └── config.toml          # Dark theme and headless server configuration
├── docs/
│   ├── ARCHITECTURE.md      # Detailed system architecture
│   ├── Implementation-plan.md # 4-week execution roadmap
│   ├── edge-case.md         # Failure mode catalog & mitigations
│   └── Problem statement.txt# Original project specification
├── raw/                     # Ingested raw captures (JSON)
├── wiki/                    # Processed personal wiki notes (PARA)
│   ├── Projects/
│   ├── Areas/
│   ├── Resources/
│   └── Archives/
├── src/
│   ├── utils/               # Scrapers and document extractors
│   ├── capture.py           # Week 1 capture CLI & engine
│   ├── classify.py          # Week 2 LLM PARA classifier
│   ├── link.py              # Week 2 local embedding auto-linker
│   ├── build_graph.py       # Week 3 graph compiler
│   └── ask.py               # Week 4 grounded RAG engine
├── static/                  # HTML templates & visualizer assets
├── app.py                   # Week 4 Streamlit unified UI
├── requirements.txt         # Pinned dependencies
├── .env.example             # Environment variables template
└── .gitignore               # Ignored secrets & caches
```

---

## 🚀 Quickstart

1. **Clone & Setup Environment:**
   ```bash
   uv venv .venv
   .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Add your GROQ_API_KEY to .env
   ```

3. **Launch the Streamlit Web Application:**
   ```bash
   streamlit run app.py
   ```
   Open `http://localhost:8501` to view the interactive dashboard with:
   - **🔮 Ask Your Brain:** Conversational grounded Q&A with live streaming tokens and source inspection.
   - **🕸️ Living Brain:** Force-directed Vis-Network interactive graph with search and category filters.
   - **📥 Ingest Knowledge:** Multi-source capture (Text notes, Web URLs, PDF/TXT/MD files) with automated classification.

---

## 💻 CLI Commands

SecondSelf provides complete command-line tools for every pipeline stage:

- **Capture new content:**
  ```bash
  python capture.py -t "Meeting notes or thought snippet"
  python capture.py -u "https://en.wikipedia.org/wiki/Memex"
  python capture.py -f "path/to/document.pdf"
  ```

- **Auto-classify raw captures into PARA:**
  ```bash
  python classify.py --all
  ```

- **Auto-link notes using semantic vector embeddings:**
  ```bash
  python link.py --threshold 0.65 --max-links 3
  ```

- **Compile interactive knowledge graph:**
  ```bash
  python build_graph.py
  # Generates graph.json and standalone graph.html
  ```

- **Ask questions via grounded RAG in terminal:**
  ```bash
  python ask.py "What is the PARA framework?"
  ```

- **Inspect vector embeddings and similarity matrix:**
  ```bash
  python view_embeddings.py
  ```

---

## ☁️ Cloud Deployment (Streamlit Community Cloud)

To deploy SecondSelf as a public web application:

1. Push your repository to GitHub:
   ```bash
   git push origin main
   ```
2. Navigate to [share.streamlit.io](https://share.streamlit.io).
3. Connect your GitHub account and click **New app**.
4. Select repository `Second-Brain`, branch `main`, and main file path `app.py`.
5. Under **Advanced Settings > Secrets**, add your Groq API key:
   ```toml
   GROQ_API_KEY = "your-groq-api-key"
   ```
6. Click **Deploy!** Your Second Brain will be live with a public HTTPS URL.

