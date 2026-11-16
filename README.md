# SecondSelf: Your Personal AI Second Brain

> A personal knowledge engine that captures anything, organizes itself with the PARA method, auto-links related thoughts with dense vector embeddings, renders a living visual brain, and answers questions grounded in your own notes.

---

## 🧭 Milestone Badges & Progress

- [x] **Phase 0: Scaffolding & Setup** — Directory trees, environment configs, pinned dependencies.
- [x] **Week 1: The Archivist 🏅** — Robust multi-source capture pipeline (`raw/` vault populated with 12 real captures).
- [ ] **Week 2: The Librarian 🏅** — Automated PARA classification and semantic auto-linking (`wiki/` vault).
- [ ] **Week 3: The Cartographer 🏅** — Interactive force-directed knowledge graph (`vis-network`).
- [ ] **Week 4: The Oracle 🏅** — Grounded RAG synthesis and public Streamlit deployment.

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
