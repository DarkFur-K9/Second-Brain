---
id: "20261116-113704-6aa05d"
title: "Streamlit Caching and State Patterns"
para_category: "Resources"
tags:
  - "streamlit"
  - "python"
  - "caching"
  - "state-management"
  - "web-apps"
summary: "Best practices for managing Streamlit application state and performance, specifically distinguishing between resource caching, data caching, and session state usage."
created_at: "2026-11-16T11:37:04.749969+00:00"
source_type: "text"
source_ref: "manual"
links: []
---

# Streamlit Caching and State Patterns

## Streamlit Architecture Patterns

- **Heavy Resources**: Use `st.cache_resource` for heavy, non-serializable objects (e.g., PyTorch models, SentenceTransformers, database pools) to ensure they load only once per process.
- **Computation Results**: Use `st.cache_data` for caching computation results or DataFrames.
- **User State**: Keep user-specific state strictly in `st.session_state` to prevent cross-session pollution.

## Related Notes
*(No related notes found above similarity threshold)*