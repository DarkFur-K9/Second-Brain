"""SecondSelf: Semantic Auto-Linking Engine (The Librarian - Task 2.2).

Computes local vector embeddings (all-MiniLM-L6-v2) for all notes in wiki/,
calculates cosine similarity between notes, and auto-inserts [[wikilinks]]
into frontmatter and the '## Related Notes' section.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv

load_dotenv()

DEFAULT_WIKI_DIR = Path("wiki")
DEFAULT_CACHE_FILE = DEFAULT_WIKI_DIR / ".embeddings.npz"
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.65"))
DEFAULT_MAX_LINKS = int(os.getenv("MAX_RELATED_LINKS", "3"))
UPPER_SIMILARITY_CUTOFF = 0.98  # Avoid linking near-duplicates


class WikiNote:
    """Represents a parsed Markdown note in the wiki."""

    def __init__(self, path: Path, raw_text: str):
        self.path = path
        self.slug = path.stem
        self.raw_text = raw_text
        self.frontmatter_dict, self.body = self._parse_frontmatter(raw_text)
        self.id = self.frontmatter_dict.get("id", self.slug)
        self.title = self.frontmatter_dict.get("title", self.slug.replace("-", " ").title())
        self.category = self.frontmatter_dict.get("para_category", path.parent.name)
        self.tags = self.frontmatter_dict.get("tags", [])
        self.summary = self.frontmatter_dict.get("summary", "")
        self.content_hash = self._compute_hash()

    def _parse_frontmatter(self, text: str) -> Tuple[Dict[str, Any], str]:
        """Extract YAML frontmatter and body."""
        fm_dict: Dict[str, Any] = {}
        body = text

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if match:
            fm_text, body = match.group(1), match.group(2)
            # Basic YAML parsing for known frontmatter keys
            for line in fm_text.splitlines():
                line = line.strip()
                if line.startswith("id:"):
                    fm_dict["id"] = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("title:"):
                    fm_dict["title"] = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("para_category:"):
                    fm_dict["para_category"] = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("summary:"):
                    fm_dict["summary"] = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("created_at:"):
                    fm_dict["created_at"] = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("source_type:"):
                    fm_dict["source_type"] = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("source_ref:"):
                    fm_dict["source_ref"] = line.split(":", 1)[1].strip().strip('"\'')

            # Extract tags
            tags_match = re.search(r"tags:\s*\n((?:\s*-\s*.*?\n)+)", fm_text)
            if tags_match:
                tags = [
                    t.strip().lstrip("-").strip().strip('"\'')
                    for t in tags_match.group(1).splitlines()
                    if t.strip()
                ]
                fm_dict["tags"] = tags

        return fm_dict, body

    def get_embedding_text(self) -> str:
        """Construct dense text representation for semantic embedding."""
        tags_str = ", ".join(self.tags) if isinstance(self.tags, list) else str(self.tags)
        # Strip existing Related Notes section from body so it doesn't feed back into embeddings
        clean_body = re.sub(r"## Related Notes.*$", "", self.body, flags=re.DOTALL).strip()
        body_preview = clean_body[:500]
        return f"{self.title}\n{self.summary}\nTags: {tags_str}\n\n{body_preview}".strip()

    def _compute_hash(self) -> str:
        """SHA-256 fingerprint of the embedding representation."""
        text = self.get_embedding_text()
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_embedding_model():
    """Load all-MiniLM-L6-v2 sentence-transformers model."""
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    except Exception:
        return SentenceTransformer("all-MiniLM-L6-v2")


def load_cached_embeddings(cache_file: Path) -> Tuple[Dict[str, str], Dict[str, np.ndarray]]:
    """
    Load cached embeddings from .embeddings.npz.
    Returns (path_to_hash_dict, path_to_embedding_dict).
    """
    if not cache_file.exists():
        return {}, {}

    try:
        data = np.load(cache_file, allow_pickle=True)
        paths = [str(p) for p in data["paths"]]
        hashes = [str(h) for h in data["hashes"]]
        embeddings = data["embeddings"]

        hash_map = dict(zip(paths, hashes))
        emb_map = {p: embeddings[i] for i, p in enumerate(paths)}
        return hash_map, emb_map
    except Exception as e:
        print(f"    [!] Warning: Failed to load embeddings cache ({e}). Rebuilding.")
        return {}, {}


def save_cached_embeddings(
    cache_file: Path,
    path_to_hash: Dict[str, str],
    path_to_emb: Dict[str, np.ndarray],
) -> None:
    """Save embeddings cache to .embeddings.npz."""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        paths = list(path_to_emb.keys())
        hashes = [path_to_hash.get(p, "") for p in paths]
        embeddings = np.array([path_to_emb[p] for p in paths], dtype=np.float32)

        np.savez_compressed(
            cache_file,
            paths=np.array(paths),
            hashes=np.array(hashes),
            embeddings=embeddings,
        )
    except Exception as e:
        print(f"    [!] Warning: Could not save embeddings cache: {e}")


def load_wiki_notes(wiki_dir: Path) -> List[WikiNote]:
    """Scan all markdown files in wiki/ and subdirectories."""
    notes = []
    for md_file in sorted(wiki_dir.rglob("*.md")):
        # Skip template or hidden files
        if md_file.name.startswith((".", "_")):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            notes.append(WikiNote(md_file, content))
        except Exception as e:
            print(f"[!] Error reading note {md_file.name}: {e}")
    return notes


def compute_note_embeddings(
    notes: List[WikiNote],
    cache_file: Path = DEFAULT_CACHE_FILE,
    force_recompute: bool = False,
) -> Dict[str, np.ndarray]:
    """
    Compute 384-dimensional dense vectors for all notes using local MiniLM.
    Employs SHA-256 caching to skip unmodified notes.
    """
    cached_hashes, cached_embs = ({}, {}) if force_recompute else load_cached_embeddings(cache_file)

    to_encode: List[Tuple[str, str]] = []  # (path_key, text)
    embeddings_map: Dict[str, np.ndarray] = {}
    updated_hashes: Dict[str, str] = {}

    for note in notes:
        path_key = str(note.path.as_posix())
        updated_hashes[path_key] = note.content_hash

        if (
            not force_recompute
            and path_key in cached_embs
            and cached_hashes.get(path_key) == note.content_hash
        ):
            embeddings_map[path_key] = cached_embs[path_key]
        else:
            to_encode.append((path_key, note.get_embedding_text()))

    if to_encode:
        print(f"[*] Computing embeddings for {len(to_encode)} new/modified note(s)...")
        model = get_embedding_model()
        texts = [item[1] for item in to_encode]
        new_vectors = model.encode(texts, show_progress_bar=len(texts) > 5, normalize_embeddings=True)

        for i, (path_key, _) in enumerate(to_encode):
            embeddings_map[path_key] = new_vectors[i]

        save_cached_embeddings(cache_file, updated_hashes, embeddings_map)
        print(f"    [OK] Cached embeddings updated in {cache_file}")
    else:
        print(f"[*] All {len(notes)} note embeddings loaded from cache.")

    return embeddings_map


def compute_similarity_matrix(
    notes: List[WikiNote],
    embeddings_map: Dict[str, np.ndarray],
) -> np.ndarray:
    """Compute pairwise cosine similarity matrix."""
    vectors = []
    for note in notes:
        vec = embeddings_map[str(note.path.as_posix())]
        norm = np.linalg.norm(vec)
        vectors.append(vec / norm if norm > 0 else vec)

    matrix = np.array(vectors, dtype=np.float32)
    # Cosine similarity between normalized vectors is dot product
    return np.dot(matrix, matrix.T)


def update_note_links(
    note: WikiNote,
    related_notes: List[Tuple[WikiNote, float]],
    dry_run: bool = False,
) -> None:
    """
    Inject [[wikilinks]] into the YAML frontmatter and update ## Related Notes section.
    """
    raw = note.raw_text

    # Extract target slugs
    target_slugs = [rn.slug for rn, _ in related_notes]
    links_yaml = "\n".join(f'  - "[[{s}]]"' for s in target_slugs)

    # 1. Update frontmatter links: []
    if "links:" in raw:
        # Replace existing links block
        raw = re.sub(
            r"links:\s*(?:\[\]|(?:\n\s*-\s*\"?\[\[.*?\]\]\"?)+)",
            f"links:\n{links_yaml}" if target_slugs else "links: []",
            raw,
        )
    else:
        # Insert links before closing frontmatter
        raw = re.sub(
            r"\n---\s*\n",
            f"\nlinks:\n{links_yaml}\n---\n" if target_slugs else "\nlinks: []\n---\n",
            raw,
            count=1,
        )

    # 2. Build Related Notes Markdown section
    if related_notes:
        items = [
            f"- [[{rn.slug}]] (similarity: {sim:.2f}) - *{rn.title}*"
            for rn, sim in related_notes
        ]
        related_section = "## Related Notes\n" + "\n".join(items) + "\n"
    else:
        related_section = "## Related Notes\n*(No related notes found above similarity threshold)*\n"

    # Replace existing Related Notes section or append at end
    if "## Related Notes" in raw:
        raw = re.sub(r"## Related Notes.*$", related_section.strip(), raw, flags=re.DOTALL)
    else:
        raw = raw.rstrip() + "\n\n" + related_section

    if not dry_run:
        note.path.write_text(raw, encoding="utf-8")


def auto_link_wiki(
    wiki_dir: Path = DEFAULT_WIKI_DIR,
    cache_file: Path = DEFAULT_CACHE_FILE,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_links: int = DEFAULT_MAX_LINKS,
    force_recompute: bool = False,
    dry_run: bool = False,
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Main auto-linking pipeline.
    Finds related notes for every note in wiki/ and updates frontmatter + links.
    """
    notes = load_wiki_notes(wiki_dir)
    if len(notes) < 2:
        print(f"[i] Need at least 2 notes to establish links. Found {len(notes)} note(s).")
        return {}

    print(f"\n{'='*65}")
    print(f" SecondSelf: Semantic Auto-Linking Engine (The Librarian)")
    print(f"{'='*65}")
    print(f"Vault notes found:     {len(notes)}")
    print(f"Similarity threshold:  >= {threshold}")
    print(f"Max links per note:    {max_links}")
    print(f"Embeddings cache:      {cache_file}")
    print(f"{'='*65}\n")

    embeddings_map = compute_note_embeddings(notes, cache_file, force_recompute=force_recompute)
    sim_matrix = compute_similarity_matrix(notes, embeddings_map)

    link_results: Dict[str, List[Tuple[str, float]]] = {}
    total_links_created = 0

    print("\n--- Connecting The Dots ---")
    for i, note in enumerate(notes):
        # Find related notes
        candidates: List[Tuple[WikiNote, float]] = []
        for j, other_note in enumerate(notes):
            if i == j:
                continue  # Skip self
            sim = float(sim_matrix[i, j])
            # Filter within threshold band
            if threshold <= sim <= UPPER_SIMILARITY_CUTOFF:
                candidates.append((other_note, sim))

        # Sort descending by similarity score, take top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        matched = candidates[:max_links]

        link_results[note.slug] = [(m[0].slug, m[1]) for m in matched]
        total_links_created += len(matched)

        # Print linkage info
        print(f"[+] {note.slug} ({note.category})")
        if matched:
            for target_note, score in matched:
                print(f"    └──> [[{target_note.slug}]] ({score:.2f}) - {target_note.title}")
        else:
            print("    └── (No strong connections found)")

        update_note_links(note, matched, dry_run=dry_run)

    print(f"\n{'='*65}")
    status_msg = "[DRY RUN] Would create" if dry_run else "[OK] Successfully linked"
    print(f" {status_msg} {total_links_created} bidirectional link(s) across {len(notes)} notes.")
    print(f"{'='*65}\n")

    return link_results


def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="SecondSelf: Semantic Auto-Linker (The Librarian - Task 2.2)."
    )
    parser.add_argument(
        "--wiki-dir",
        type=str,
        default="wiki",
        help="Path to wiki directory containing PARA notes (default: wiki).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Cosine similarity threshold (default: {DEFAULT_SIMILARITY_THRESHOLD}).",
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=DEFAULT_MAX_LINKS,
        help=f"Max related links per note (default: {DEFAULT_MAX_LINKS}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recompute all embeddings from scratch, ignoring cache.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate links and display output without writing to markdown files.",
    )

    args = parser.parse_args()
    wiki_path = Path(args.wiki_dir)

    auto_link_wiki(
        wiki_dir=wiki_path,
        cache_file=wiki_path / ".embeddings.npz",
        threshold=args.threshold,
        max_links=args.max_links,
        force_recompute=args.force,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
