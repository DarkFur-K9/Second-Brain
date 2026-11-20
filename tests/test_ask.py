"""Automated unit tests for Task 4.1: Natural Language RAG Engine (The Oracle)."""

import tempfile
import shutil
import unittest
from pathlib import Path

from src.ask import (
    RetrievalResult,
    AskResponse,
    build_rag_system_prompt,
    build_rag_user_prompt,
    ask,
)


class TestAskModule(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.wiki_dir = self.test_dir / "wiki"
        self.wiki_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_out_of_domain_query_fallback(self):
        """TEST-EC-08: When no notes exceed min similarity, system avoids hallucination."""
        empty_cache = self.wiki_dir / ".embeddings.npz"
        # Run ask() with empty wiki
        res = ask(
            query="What is the capital of Mongolia?",
            wiki_dir=self.wiki_dir,
            cache_file=empty_cache,
            min_similarity=0.40,
        )
        self.assertFalse(res.grounded)
        self.assertEqual(len(res.sources), 0)
        self.assertIn("couldn't find any relevant notes", res.answer.lower())

    def test_empty_query_handling(self):
        """Verify empty string or whitespace input is handled gracefully."""
        res = ask(query="   ", wiki_dir=self.wiki_dir)
        self.assertFalse(res.grounded)
        self.assertIn("valid question", res.answer)

    def test_build_rag_user_prompt(self):
        """Verify XML context boundaries and formatting."""
        sources = [
            RetrievalResult(
                slug="test-slug",
                title="Test Note",
                category="Projects",
                similarity=0.88,
                path="wiki/Projects/test.md",
                summary="A test note summary.",
                created_at="2026-11-20T12:00:00Z",
                content_excerpt="This is important project content.",
            )
        ]

        prompt = build_rag_user_prompt("How does the test work?", sources)
        self.assertIn("<user_note_context>", prompt)
        self.assertIn("Title: Test Note", prompt)
        self.assertIn("Category: Projects | Created: 2026-11-20T12:00:00Z", prompt)
        self.assertIn("This is important project content.", prompt)
        self.assertIn("</user_note_context>", prompt)
        self.assertIn("User Question: How does the test work?", prompt)

    def test_system_prompt_rules(self):
        """Verify system prompt enforces grounding and wikilinks."""
        sys_prompt = build_rag_system_prompt()
        self.assertIn("SecondSelf", sys_prompt)
        self.assertIn("[[Note Title]]", sys_prompt)
        self.assertIn("<user_note_context>", sys_prompt)


if __name__ == "__main__":
    unittest.main()
