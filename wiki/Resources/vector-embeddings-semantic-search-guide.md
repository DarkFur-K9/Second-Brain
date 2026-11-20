---
id: "20261116-113643-9f0014"
title: "Vector Embeddings Semantic Search Guide"
para_category: "Resources"
tags:
  - "vector-embeddings"
  - "semantic-search"
  - "nlp"
  - "sentence-transformers"
  - "machine-learning"
summary: "Explains how SentenceTransformers maps sentences to 384-dimensional vectors for semantic search. Highlights the use of cosine similarity to capture conceptual meaning over exact keyword matching."
created_at: "2026-11-16T11:36:43.470917+00:00"
source_type: "text"
source_ref: "manual"
links:
  - "[[vector-embeddings-semantic-search]]"
---

# Vector Embeddings Semantic Search Guide

## Vector Embeddings & Semantic Search

### Core Concept
- **Model**: `SentenceTransformers` using `all-MiniLM-L6-v2`.
- **Function**: Maps sentences into a dense **384-dimensional vector space**.

### Search Mechanism
- **Metric**: Cosine similarity between vectors.
- **Benefit**: Enables semantic search that captures **conceptual meaning** rather than relying on exact keyword matches.

## Related Notes
- [[vector-embeddings-semantic-search]] (similarity: 0.93) - *Vector Embeddings & Semantic Search*