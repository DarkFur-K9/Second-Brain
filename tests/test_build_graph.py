"""Automated unit tests for Task 3.1: Graph Data Model Compiler."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.build_graph import (
    parse_note_metadata,
    extract_wikilinks_with_weights,
    build_graph_data,
    export_graph_json,
    render_graph_html,
)


class TestBuildGraph(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.wiki_dir = self.test_dir / "wiki"
        self.wiki_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_note_metadata(self):
        """Verify frontmatter parsing extracts correct fields."""
        md_text = """---
id: "note-1"
title: "FastAPI Testing Guide"
para_category: "Projects"
tags:
  - "fastapi"
  - "testing"
summary: "Guide to pytest with FastAPI."
---
# FastAPI Testing Guide
Content goes here.
"""
        note_file = self.wiki_dir / "Projects" / "fastapi-testing.md"
        meta = parse_note_metadata(note_file, md_text)

        self.assertEqual(meta["slug"], "fastapi-testing")
        self.assertEqual(meta["label"], "FastAPI Testing Guide")
        self.assertEqual(meta["group"], "Projects")
        self.assertEqual(meta["tags"], ["fastapi", "testing"])
        self.assertEqual(meta["summary"], "Guide to pytest with FastAPI.")

    def test_extract_wikilinks_with_weights(self):
        """Verify extraction of target slugs and similarity scores."""
        content = """# Note
Here is a reference to [[intro-guide]].

## Related Notes
- [[python-best-practices]] (similarity: 0.88) - *Python Best Practices*
- [[docker-setup]] (similarity: 0.72)
"""
        links = extract_wikilinks_with_weights(content)
        targets = [target for target, _ in links]

        self.assertIn("python-best-practices", targets)
        self.assertIn("docker-setup", targets)
        self.assertIn("intro-guide", targets)

        # Check that explicit similarity was parsed
        sim_map = dict(links)
        self.assertEqual(sim_map["python-best-practices"], 0.88)
        self.assertEqual(sim_map["docker-setup"], 0.72)

    def test_build_graph_data_and_phantom_link_safety(self):
        """TEST-EC-07: Verify dangling/broken wikilinks are safely excluded."""
        # Create note A linking to note B and non-existent note C
        proj_dir = self.wiki_dir / "Projects"
        res_dir = self.wiki_dir / "Resources"
        proj_dir.mkdir(parents=True)
        res_dir.mkdir(parents=True)

        note_a_text = """---
title: "Note A"
para_category: "Projects"
summary: "Note A summary"
---
Link to [[note-b]] and phantom [[broken-link]].
"""
        note_b_text = """---
title: "Note B"
para_category: "Resources"
summary: "Note B summary"
---
Link to [[note-a]].
"""
        (proj_dir / "note-a.md").write_text(note_a_text, encoding="utf-8")
        (res_dir / "note-b.md").write_text(note_b_text, encoding="utf-8")

        graph = build_graph_data(self.wiki_dir)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["edges"]), 1)

        edge = graph["edges"][0]
        # Undirected edge connects note-a and note-b
        nodes_in_edge = {edge["from"], edge["to"]}
        self.assertEqual(nodes_in_edge, {"note-a", "note-b"})

        # Degree check
        node_a = next(n for n in graph["nodes"] if n["id"] == "note-a")
        self.assertEqual(node_a["degree"], 1)

    def test_export_graph_json(self):
        """Verify JSON export creates a valid parseable file with correct keys."""
        graph_data = {
            "nodes": [{"id": "n1", "label": "Node 1", "value": 15}],
            "edges": [],
            "stats": {"total_nodes": 1, "total_edges": 0},
        }
        out_file = self.test_dir / "test_graph.json"
        export_graph_json(graph_data, out_file)

        self.assertTrue(out_file.exists())
        loaded = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded["stats"]["total_nodes"], 1)
        self.assertEqual(loaded["nodes"][0]["id"], "n1")

    def test_render_graph_html(self):
        """Verify standalone HTML generation with embedded JSON data."""
        graph_data = {
            "nodes": [
                {
                    "id": "sample-node",
                    "label": "Sample Note",
                    "group": "Projects",
                    "summary": "Sample summary",
                    "tags": ["test"],
                }
            ],
            "edges": [],
            "stats": {"total_nodes": 1, "total_edges": 0},
        }
        out_html = self.test_dir / "graph.html"
        render_graph_html(graph_data, output_path=out_html)

        self.assertTrue(out_html.exists())
        html_content = out_html.read_text(encoding="utf-8")
        self.assertIn("SecondSelf", html_content)
        self.assertIn("sample-node", html_content)
        self.assertIn("Sample Note", html_content)
        self.assertIn("vis-network", html_content)


if __name__ == "__main__":
    unittest.main()
