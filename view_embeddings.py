"""SecondSelf: Embeddings Inspector.

Displays and analyzes dense vector embeddings stored in wiki/.embeddings.npz.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import numpy as np

DEFAULT_EMBEDDINGS_FILE = Path("wiki/.embeddings.npz")


def format_vector_preview(vec: np.ndarray, num_items: int = 5) -> str:
    """Format the first few values of a vector as a clean string."""
    first_few = [f"{val:+.4f}" for val in vec[:num_items]]
    return f"[{', '.join(first_few)}, ... +{len(vec) - num_items} dims]"


def view_embeddings(
    file_path: Path = DEFAULT_EMBEDDINGS_FILE,
    filter_note: str | None = None,
    show_full: bool = False,
    show_stats: bool = False,
    compare_notes: list[str] | None = None,
) -> None:
    """Load and display the contents of .embeddings.npz."""
    if not file_path.exists():
        print(f"[ERROR] Embeddings file not found at: {file_path}", file=sys.stderr)
        print("Run 'python link.py' first to generate embeddings for your notes.", file=sys.stderr)
        sys.exit(1)

    try:
        data = np.load(file_path, allow_pickle=True)
    except Exception as e:
        print(f"[ERROR] Failed to load {file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    paths = [str(p) for p in data["paths"]]
    hashes = [str(h) for h in data["hashes"]]
    embeddings = data["embeddings"]

    total_notes, dimensions = embeddings.shape
    file_size_kb = file_path.stat().st_size / 1024

    print("=" * 80)
    print(" SecondSelf: Stored Vector Embeddings Inspector")
    print("=" * 80)
    print(f"File location:    {file_path.resolve()}")
    print(f"File size:        {file_size_kb:.2f} KB")
    print(f"Total notes:      {total_notes}")
    print(f"Embedding dims:   {dimensions} dimensions (all-MiniLM-L6-v2)")
    print(f"Data type:        {embeddings.dtype}")
    print("=" * 80)

    # 1. Compare two notes if requested
    if compare_notes and len(compare_notes) == 2:
        n1, n2 = compare_notes
        idx1 = [i for i, p in enumerate(paths) if n1.lower() in p.lower()]
        idx2 = [i for i, p in enumerate(paths) if n2.lower() in p.lower()]

        if not idx1:
            print(f"[!] Note not found matching: '{n1}'")
            return
        if not idx2:
            print(f"[!] Note not found matching: '{n2}'")
            return

        i1, i2 = idx1[0], idx2[0]
        v1, v2 = embeddings[i1], embeddings[i2]
        # Cosine similarity (vectors are normalized)
        cos_sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

        print("\n--- Cosine Similarity Comparison ---")
        print(f"Note A: {paths[i1]}")
        print(f"Note B: {paths[i2]}")
        print(f"Cosine Similarity: {cos_sim:.4f} ({cos_sim * 100:.2f}%)")
        print("------------------------------------\n")
        return

    # 2. Show detailed vector for a single note
    if filter_note:
        matches = [i for i, p in enumerate(paths) if filter_note.lower() in p.lower()]
        if not matches:
            print(f"\n[!] No notes matched query: '{filter_note}'")
            return

        for idx in matches:
            p = paths[idx]
            vec = embeddings[idx]
            h = hashes[idx]
            norm = float(np.linalg.norm(vec))

            print(f"\n[NOTE DETAILS] {p}")
            print(f"Content SHA-256: {h}")
            print(f"Vector L2 Norm:  {norm:.4f} (1.0 = unit normalized)")
            print(f"Min / Max / Mean: {vec.min():+.4f} / {vec.max():+.4f} / {vec.mean():+.4f}")
            print("\nVector Coordinates (384 dimensions):")
            print("-" * 80)
            # Print 8 dimensions per row
            for row_start in range(0, len(vec), 8):
                chunk = vec[row_start : row_start + 8]
                formatted = " ".join(f"{val:+.4f}" for val in chunk)
                print(f"[{row_start:03d}-{row_start+len(chunk)-1:03d}]: {formatted}")
            print("-" * 80)
        return

    # 3. Overall statistical distribution
    if show_stats:
        print("\n--- Global Embedding Space Distribution ---")
        print(f"Overall Minimum:  {embeddings.min():+.6f}")
        print(f"Overall Maximum:  {embeddings.max():+.6f}")
        print(f"Overall Mean:     {embeddings.mean():+.6f}")
        print(f"Standard Dev:     {embeddings.std():+.6f}")
        print("-------------------------------------------\n")

    # 4. Standard list view of all notes
    print(f"\n{'#':<3} | {'NOTE PATH':<42} | {'VECTOR PREVIEW (First 5 dims)':<30}")
    print("-" * 80)
    for i, (path_str, vec) in enumerate(zip(paths, embeddings), 1):
        clean_path = path_str.replace("wiki/", "").replace("wiki\\", "")
        # Truncate path if too long
        if len(clean_path) > 40:
            clean_path = "..." + clean_path[-37:]

        preview = format_vector_preview(vec, num_items=3 if not show_full else 5)
        print(f"{i:<3} | {clean_path:<42} | {preview}")

    print("-" * 80)
    print("\nTips:")
    print("  View full 384 dimensions of a note:  python view_embeddings.py --note <keyword>")
    print("  Compare similarity of two notes:     python view_embeddings.py --compare <note1> <note2>")
    print("  Show distribution statistics:        python view_embeddings.py --stats\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SecondSelf: Stored Vector Embeddings Inspector."
    )
    parser.add_argument(
        "--file",
        type=str,
        default=str(DEFAULT_EMBEDDINGS_FILE),
        help="Path to .npz embeddings file (default: wiki/.embeddings.npz)",
    )
    parser.add_argument(
        "--note",
        "-n",
        type=str,
        default=None,
        help="Filter and view the full 384 dimensions for a specific note (keyword search)",
    )
    parser.add_argument(
        "--stats",
        "-s",
        action="store_true",
        help="Show statistical summary of the embedding space",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show more dimensions in the table preview",
    )
    parser.add_argument(
        "--compare",
        "-c",
        nargs=2,
        metavar=("NOTE1", "NOTE2"),
        help="Compute and display cosine similarity between two notes from their embeddings",
    )

    args = parser.parse_args()
    view_embeddings(
        file_path=Path(args.file),
        filter_note=args.note,
        show_full=args.full,
        show_stats=args.stats,
        compare_notes=args.compare,
    )


if __name__ == "__main__":
    main()
