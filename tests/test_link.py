"""Automated unit tests for Task 2.2: Semantic Auto-Linker."""

import tempfile
import shutil
import unittest
from pathlib import Path
import numpy as np

from src.link import (
    WikiNote,
    compute_similarity_matrix,
    update_note_links,
    load_cached_embeddings,
    save_cached_embeddings,
)


class TestLinkModule(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.wiki_dir = self.test_dir / "wiki"
        self.wiki_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_wikinote_parsing(self):
        """Verify frontmatter parsing and text representation."""
        md_content = """---
id: "note-1"
title: "Python Best Practices"
para_category: "Resources"
tags:
  - "python"
  - "coding"
summary: "Writing clean, modular Python."
links: []
---

# Python Best Practices
Code should be readable and clean.

## Related Notes
*(old notes)*
"""
        note_file = self.wiki_dir / "python-best-practices.md"
        note_file.write_text(md_content, encoding="utf-8")

        note = WikiNote(note_file, md_content)
        self.assertEqual(note.id, "note-1")
        self.assertEqual(note.title, "Python Best Practices")
        self.assertEqual(note.category, "Resources")
        self.assertIn("python", note.tags)
        self.assertIn("Python Best Practices", note.get_embedding_text())
        # Ensure '## Related Notes' was stripped from embedding text
        self.assertNotIn("(old notes)", note.get_embedding_text())

    def test_similarity_computation(self):
        """Verify cosine similarity matrix computation."""
        note1 = WikiNote(self.wiki_dir / "n1.md", "# N1")
        note2 = WikiNote(self.wiki_dir / "n2.md", "# N2")

        # Two identical vectors -> similarity 1.0
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        emb_map = {
            str(note1.path.as_posix()): v1,
            str(note2.path.as_posix()): v2,
        }

        sim_matrix = compute_similarity_matrix([note1, note2], emb_map)
        self.assertAlmostEqual(sim_matrix[0, 1], 1.0, places=4)

    def test_update_note_links(self):
        """Verify link injection in frontmatter and ## Related Notes section."""
        md_content = """---
id: "source-note"
title: "Source Note"
para_category: "Projects"
tags:
  - "ai"
summary: "AI note"
links: []
---

# Source Note
Content goes here.

## Related Notes
*(Old text)*
"""
        note_file = self.wiki_dir / "source-note.md"
        note_file.write_text(md_content, encoding="utf-8")
        note = WikiNote(note_file, md_content)

        target_file = self.wiki_dir / "target-note.md"
        target_note = WikiNote(target_file, "# Target Note")

        update_note_links(note, [(target_note, 0.85)], dry_run=False)

        updated_text = note_file.read_text(encoding="utf-8")
        self.assertIn('  - "[[target-note]]"', updated_text)
        self.assertIn("- [[target-note]] (similarity: 0.85)", updated_text)
        self.assertNotIn("*(Old text)*", updated_text)

    def test_embeddings_cache_save_and_load(self):
        """Verify saving and reading cache .embeddings.npz."""
        cache_file = self.wiki_dir / ".embeddings.npz"
        path_to_hash = {"wiki/note1.md": "hash1", "wiki/note2.md": "hash2"}
        path_to_emb = {
            "wiki/note1.md": np.array([0.1, 0.2], dtype=np.float32),
            "wiki/note2.md": np.array([0.3, 0.4], dtype=np.float32),
        }

        save_cached_embeddings(cache_file, path_to_hash, path_to_emb)
        self.assertTrue(cache_file.exists())

        loaded_hashes, loaded_embs = load_cached_embeddings(cache_file)
        self.assertEqual(loaded_hashes["wiki/note1.md"], "hash1")
        np.testing.assert_array_almost_equal(loaded_embs["wiki/note2.md"], np.array([0.3, 0.4], dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
