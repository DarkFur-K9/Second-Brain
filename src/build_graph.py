"""SecondSelf: Graph Data Model Compiler (The Cartographer - Task 3.1).

Scans all notes in wiki/, parses YAML frontmatter and [[wikilinks]],
calculates degree centrality, and exports clean nodes-and-edges JSON for visualization.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_WIKI_DIR = Path("wiki")
DEFAULT_OUTPUT_FILE = Path("graph.json")
DEFAULT_HTML_TEMPLATE = Path("static/graph_template.html")
DEFAULT_HTML_OUTPUT = Path("graph.html")

# Visual color mapping for PARA taxonomy (high-contrast palette)
PARA_COLORS = {
    "Projects": {
        "background": "#EF4444",  # Red
        "border": "#DC2626",
        "highlight": {"background": "#F87171", "border": "#B91C1C"},
    },
    "Areas": {
        "background": "#3B82F6",  # Blue
        "border": "#2563EB",
        "highlight": {"background": "#60A5FA", "border": "#1D4ED8"},
    },
    "Resources": {
        "background": "#10B981",  # Green
        "border": "#059669",
        "highlight": {"background": "#34D399", "border": "#047857"},
    },
    "Archives": {
        "background": "#6B7280",  # Gray
        "border": "#4B5563",
        "highlight": {"background": "#9CA3AF", "border": "#374151"},
    },
}

DEFAULT_COLOR = {
    "background": "#8B5CF6",  # Purple for uncategorized
    "border": "#7C3AED",
    "highlight": {"background": "#A78BFA", "border": "#6D28D9"},
}


def parse_note_metadata(md_path: Path, raw_text: str) -> Dict[str, Any]:
    """Parse YAML frontmatter, title, category, tags, and summary from markdown."""
    slug = md_path.stem
    meta: Dict[str, Any] = {
        "id": slug,
        "slug": slug,
        "path": str(md_path.as_posix()),
        "label": slug.replace("-", " ").title(),
        "group": md_path.parent.name if md_path.parent.name in PARA_COLORS else "Resources",
        "summary": "",
        "tags": [],
        "created_at": "",
    }

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, re.DOTALL)
    if match:
        fm_text, _ = match.group(1), match.group(2)
        for line in fm_text.splitlines():
            line = line.strip()
            if line.startswith("id:"):
                meta["id"] = line.split(":", 1)[1].strip().strip('"\'')
            elif line.startswith("title:"):
                meta["label"] = line.split(":", 1)[1].strip().strip('"\'')
            elif line.startswith("para_category:"):
                cat = line.split(":", 1)[1].strip().strip('"\'')
                if cat in PARA_COLORS:
                    meta["group"] = cat
            elif line.startswith("summary:"):
                meta["summary"] = line.split(":", 1)[1].strip().strip('"\'')
            elif line.startswith("created_at:"):
                meta["created_at"] = line.split(":", 1)[1].strip().strip('"\'')

        # Tags extraction
        tags_match = re.search(r"tags:\s*\n((?:\s*-\s*.*?\n)+)", fm_text)
        if tags_match:
            tags = [
                t.strip().lstrip("-").strip().strip('"\'')
                for t in tags_match.group(1).splitlines()
                if t.strip()
            ]
            meta["tags"] = tags

    return meta


def extract_wikilinks_with_weights(raw_text: str) -> List[Tuple[str, float]]:
    """
    Extract all target slugs and optional similarity scores from wikilinks.
    Handles:
      - [[target-slug]] (similarity: 0.85)
      - [[target-slug]]
      - links: list in frontmatter
    """
    links: List[Tuple[str, float]] = []
    seen_targets: Set[str] = set()

    # 1. Search in Related Notes section for explicit similarity scores
    rel_section = re.search(r"## Related Notes\s*\n(.*?)(?:\n##|\Z)", raw_text, re.DOTALL)
    if rel_section:
        matches = re.findall(
            r"\[\[([a-zA-Z0-9_\-]+)\]\](?:\s*\(similarity:\s*([\d\.]+)\))?",
            rel_section.group(1),
        )
        for target, sim_str in matches:
            weight = float(sim_str) if sim_str else 0.75
            links.append((target, weight))
            seen_targets.add(target)

    # 2. Search anywhere else in note for additional [[wikilinks]]
    all_links = re.findall(r"\[\[([a-zA-Z0-9_\-]+)\]\]", raw_text)
    for target in all_links:
        if target not in seen_targets:
            links.append((target, 0.70))
            seen_targets.add(target)

    return links


def build_graph_data(
    wiki_dir: Path = DEFAULT_WIKI_DIR,
) -> Dict[str, Any]:
    """
    Traverse wiki/, compile nodes and edges, compute degrees, and validate references.
    """
    notes_meta: Dict[str, Dict[str, Any]] = {}
    raw_edges: List[Tuple[str, str, float]] = []

    if not wiki_dir.exists():
        print(f"[!] Wiki directory not found: {wiki_dir}")
        return {"nodes": [], "edges": [], "stats": {}}

    md_files = sorted(wiki_dir.rglob("*.md"))
    for md_file in md_files:
        if md_file.name.startswith((".", "_")):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            meta = parse_note_metadata(md_file, content)
            notes_meta[meta["slug"]] = meta

            links = extract_wikilinks_with_weights(content)
            for target_slug, weight in links:
                raw_edges.append((meta["slug"], target_slug, weight))
        except Exception as e:
            print(f"[!] Error processing note {md_file.name}: {e}")

    valid_slugs = set(notes_meta.keys())
    edge_set: Set[Tuple[str, str]] = set()
    validated_edges: List[Dict[str, Any]] = []
    degrees: Dict[str, int] = {slug: 0 for slug in valid_slugs}

    # Deduplicate and validate edges (Edge Case 3.1: Phantom / Broken wikilinks)
    for source_slug, target_slug, weight in raw_edges:
        # Avoid self-loops
        if source_slug == target_slug:
            continue

        # Check if target note exists in vault
        if target_slug not in valid_slugs:
            # Ghost / broken link: omit edge to protect visualizer
            continue

        # Undirected edge deduplication key
        edge_key = tuple(sorted([source_slug, target_slug]))
        if edge_key in edge_set:
            continue
        edge_set.add(edge_key)

        degrees[source_slug] += 1
        degrees[target_slug] += 1

        validated_edges.append({
            "from": source_slug,
            "to": target_slug,
            "weight": round(weight, 2),
            "title": f"Similarity: {weight:.2f}",
            "value": round(weight, 2),
            "color": {"color": "#4B5563", "highlight": "#93C5FD", "hover": "#60A5FA"},
        })

    # Build node objects with dynamic scaling and HTML tooltip card
    nodes: List[Dict[str, Any]] = []
    for slug, meta in notes_meta.items():
        deg = degrees.get(slug, 0)
        # Dynamic node size scaled by degree centrality: 12 + 5 * deg
        node_size = 12 + min(deg * 5, 40)
        group = meta["group"]
        palette = PARA_COLORS.get(group, DEFAULT_COLOR)

        # XSS-safe sanitized summary & tags for hover tooltip
        safe_title = html.escape(meta["label"])
        safe_summary = html.escape(meta["summary"] or "No summary available.")
        safe_tags = [html.escape(t) for t in meta["tags"]]
        tags_badge_html = " ".join(
            f"<span style='background:#374151;color:#E5E7EB;padding:2px 6px;border-radius:4px;font-size:11px;'>#{t}</span>"
            for t in safe_tags
        )

        tooltip_html = (
            f"<div style='font-family:sans-serif;max-width:280px;padding:8px;'>"
            f"<div style='font-weight:bold;font-size:14px;color:#F9FAFB;margin-bottom:4px;'>{safe_title}</div>"
            f"<div style='margin-bottom:6px;'><span style='background:{palette['background']};color:#FFF;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:bold;'>{group}</span>"
            f" <span style='color:#9CA3AF;font-size:11px;'>• {deg} link{'s' if deg != 1 else ''}</span></div>"
            f"<div style='color:#D1D5DB;font-size:12px;line-height:1.4;margin-bottom:6px;'>{safe_summary}</div>"
            f"<div>{tags_badge_html}</div>"
            f"</div>"
        )

        nodes.append({
            "id": slug,
            "label": meta["label"],
            "group": group,
            "title": tooltip_html,  # Rendered on hover by vis-network
            "summary": meta["summary"],
            "tags": meta["tags"],
            "path": meta["path"],
            "degree": deg,
            "value": node_size,
            "color": palette,
            "font": {"color": "#F3F4F6", "size": 13, "face": "Inter, sans-serif"},
            "shape": "dot",
        })

    # Aggregate statistics
    cat_counts = {}
    for n in nodes:
        cat_counts[n["group"]] = cat_counts.get(n["group"], 0) + 1

    graph_data = {
        "nodes": nodes,
        "edges": validated_edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(validated_edges),
            "categories": cat_counts,
        },
    }
    return graph_data


def export_graph_json(
    graph_data: Dict[str, Any],
    output_path: Path = DEFAULT_OUTPUT_FILE,
) -> Path:
    """Save clean serialized JSON to target output path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
    temp_path.replace(output_path)

    # Also mirror to data/graph.json if data/ directory exists
    data_dir = Path("data")
    if data_dir.exists():
        data_graph = data_dir / "graph.json"
        with open(data_graph, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)

    return output_path


def render_graph_html(
    graph_data: Dict[str, Any],
    template_path: Path = DEFAULT_HTML_TEMPLATE,
    output_path: Path = DEFAULT_HTML_OUTPUT,
) -> Path:
    """
    Render self-contained interactive Vis-Network HTML page with embedded graph data.
    Opens directly in any browser without requiring an active web server.
    """
    if not template_path.exists():
        raise FileNotFoundError(f"HTML graph template not found at: {template_path}")

    template_text = template_path.read_text(encoding="utf-8")
    embedded_json = json.dumps(graph_data, ensure_ascii=False)
    rendered_html = template_text.replace("/*{{GRAPH_DATA}}*/ null", embedded_json)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered_html, encoding="utf-8")

    # Also mirror to static/index.html
    static_index = Path("static/index.html")
    if static_index.parent.exists():
        static_index.write_text(rendered_html, encoding="utf-8")

    return output_path


def build_and_export(
    wiki_dir: Path = DEFAULT_WIKI_DIR,
    output_path: Path = DEFAULT_OUTPUT_FILE,
    html_output_path: Optional[Path] = DEFAULT_HTML_OUTPUT,
) -> Dict[str, Any]:
    """Execute complete graph build pipeline and output JSON + HTML."""
    print("=" * 65)
    print(" SecondSelf: Knowledge Graph Compiler (The Cartographer)")
    print("=" * 65)
    print(f"Reading wiki notes:   {wiki_dir.resolve()}")

    graph_data = build_graph_data(wiki_dir)
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]
    stats = graph_data["stats"]

    export_path = export_graph_json(graph_data, output_path)

    print(f"Total Nodes:          {len(nodes)}")
    print(f"Total Edges:          {len(edges)}")
    print(f"Category Breakdown:")
    for cat, count in sorted(stats.get("categories", {}).items()):
        print(f"  - {cat:<10}: {count} note(s)")
    print(f"Saved Graph JSON to:  {export_path.resolve()}")

    if html_output_path:
        html_file = render_graph_html(graph_data, output_path=html_output_path)
        print(f"Rendered Visual Brain:{html_file.resolve()}")

    print("=" * 65)
    return graph_data


def main() -> None:
    """CLI Entry Point."""
    import webbrowser

    parser = argparse.ArgumentParser(
        description="SecondSelf: Graph Data Model Compiler (The Cartographer - Task 3.1 & 3.2)."
    )
    parser.add_argument(
        "--wiki-dir",
        type=str,
        default="wiki",
        help="Source directory containing organized PARA notes (default: wiki).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="graph.json",
        help="Target output JSON file (default: graph.json).",
    )
    parser.add_argument(
        "--html",
        type=str,
        default="graph.html",
        help="Target output HTML file for interactive visualizer (default: graph.html).",
    )
    parser.add_argument(
        "--view",
        "--open",
        action="store_true",
        help="Open the interactive graph in your default web browser after compilation.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print top connected hub notes in the knowledge graph.",
    )

    args = parser.parse_args()
    wiki_path = Path(args.wiki_dir)
    output_path = Path(args.output)
    html_path = Path(args.html) if args.html else None

    graph_data = build_and_export(
        wiki_dir=wiki_path,
        output_path=output_path,
        html_output_path=html_path,
    )

    if args.stats and graph_data["nodes"]:
        print("\n--- Top Connected Hub Notes ---")
        sorted_nodes = sorted(graph_data["nodes"], key=lambda x: x["degree"], reverse=True)
        for i, n in enumerate(sorted_nodes[:5], 1):
            print(f"{i}. [{n['group']}] {n['label']} ({n['degree']} connections)")
        print("-------------------------------\n")

    if args.view and html_path and html_path.exists():
        uri = html_path.resolve().as_uri()
        print(f"\n[+] Opening Interactive Living Brain in browser: {uri}\n")
        webbrowser.open(uri)


if __name__ == "__main__":
    main()
