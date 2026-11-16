"""Automated tests for Phase 1: The Archivist Capture Pipeline (Standard unittest)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.capture import capture, compute_content_hash, list_raw_captures, RawCapture
from src.utils.parsers import parse_file


class TestCapturePipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_capture_text(self):
        """Verify clean plain text capture."""
        record = capture(
            text="Test quick note for second brain.",
            title="Test Title",
            tags=["unit-test", "notes"],
            raw_dir=self.test_dir,
        )
        self.assertEqual(record.source_type, "text")
        self.assertEqual(record.title, "Test Title")
        self.assertEqual(record.tags, ["unit-test", "notes"])
        self.assertFalse(record.processed)
        self.assertTrue((self.test_dir / f"{record.id}.json").exists())

    def test_capture_empty_text_rejection(self):
        """TEST-EC-01: Rejection of empty or whitespace-only text."""
        with self.assertRaises(ValueError):
            capture(text="   \n\t  ", raw_dir=self.test_dir)

    def test_duplicate_detection(self):
        """Verify duplicate detection by content hash."""
        rec1 = capture(text="Identical content.", raw_dir=self.test_dir)
        rec2 = capture(text="Identical content.", raw_dir=self.test_dir, force=False)
        self.assertEqual(rec1.id, rec2.id)

    def test_file_parsing(self):
        """Verify file parsing on a dummy markdown file."""
        test_file = self.test_dir / "sample.md"
        test_file.write_text("# Sample Heading\n\nThis is body content.", encoding="utf-8")

        title, content, meta = parse_file(str(test_file))
        self.assertEqual(title, "Sample Heading")
        self.assertIn("This is body content.", content)
        self.assertEqual(meta["extension"], ".md")

    def test_list_captures(self):
        """Verify listing returns valid serialized records."""
        capture(text="Item 1", title="Title 1", raw_dir=self.test_dir)
        capture(text="Item 2", title="Title 2", raw_dir=self.test_dir)
        captures = list_raw_captures(self.test_dir)
        self.assertEqual(len(captures), 2)


if __name__ == "__main__":
    unittest.main()
