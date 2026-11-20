"""Automated unit tests for Task 2.1: PARA Auto-Classification."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.classify import (
    ClassificationResult,
    format_markdown_note,
    safe_slug,
    save_wiki_note,
    mark_raw_processed,
)


class TestClassifyModule(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.raw_dir = self.test_dir / "raw"
        self.wiki_dir = self.test_dir / "wiki"
        self.raw_dir.mkdir(parents=True)
        self.wiki_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_safe_slug_windows_special_chars(self):
        """TEST-EC-04: Test sanitizing Windows reserved characters."""
        title = 'What: Is AI? / Deep Dive & Guide <2026> | "Best" Practices*'
        slug = safe_slug(title)
        for char in ':*?"<>|/\\':
            self.assertNotIn(char, slug)
        self.assertEqual(slug, "what-is-ai-deep-dive-guide-2026-best-practices")

    def test_safe_slug_length_cap(self):
        """Verify long titles are capped safely."""
        long_title = "a" * 150
        slug = safe_slug(long_title)
        self.assertLessEqual(len(slug), 60)

    def test_format_markdown_note(self):
        """Verify YAML frontmatter and note formatting."""
        record = {
            "id": "20261120-120000-abcdef",
            "timestamp": "2026-11-20T12:00:00Z",
            "source_type": "text",
            "source_ref": "manual",
        }
        classification = ClassificationResult(
            title="FastAPI Lifespan Architecture",
            category="Projects",
            tags=["fastapi", "python", "backend"],
            summary="Best practices for FastAPI lifespan handlers.",
            clean_markdown="## Introduction\nLifespan handlers manage startup and shutdown.",
        )

        md = format_markdown_note(record, classification)
        self.assertIn('id: "20261120-120000-abcdef"', md)
        self.assertIn('para_category: "Projects"', md)
        self.assertIn('  - "fastapi"', md)
        self.assertIn("# FastAPI Lifespan Architecture", md)
        self.assertIn("## Related Notes", md)

    def test_save_wiki_note_and_collision_defense(self):
        """Verify notes are saved in the correct PARA directory with collision safety."""
        record1 = {"id": "note-1", "timestamp": "2026-11-20T12:00:00Z"}
        record2 = {"id": "note-2", "timestamp": "2026-11-20T12:05:00Z"}

        classification = ClassificationResult(
            title="Duplicate Title Note",
            category="Areas",
            tags=["productivity"],
            summary="A note about productivity.",
            clean_markdown="Content for note 1.",
        )

        path1 = save_wiki_note(record1, classification, wiki_dir=self.wiki_dir)
        self.assertTrue(path1.exists())
        self.assertEqual(path1.parent.name, "Areas")
        self.assertEqual(path1.name, "duplicate-title-note.md")

        # Second note with same title but different ID should have collision defense
        path2 = save_wiki_note(record2, classification, wiki_dir=self.wiki_dir)
        self.assertTrue(path2.exists())
        self.assertNotEqual(path1, path2)
        self.assertTrue(path2.name.startswith("duplicate-title-note-"))

    def test_mark_raw_processed(self):
        """Verify raw capture JSON is updated with processed: true."""
        raw_file = self.raw_dir / "sample.json"
        raw_file.write_text(
            json.dumps({"id": "sample-1", "processed": False}), encoding="utf-8"
        )

        mark_raw_processed(raw_file)
        updated = json.loads(raw_file.read_text(encoding="utf-8"))
        self.assertTrue(updated["processed"])


if __name__ == "__main__":
    unittest.main()
