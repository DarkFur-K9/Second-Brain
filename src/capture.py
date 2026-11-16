"""SecondSelf: Frictionless Multi-Source Ingestion Pipeline (The Archivist)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

# Support both package and direct script execution
try:
    from src.utils.parsers import parse_file
    from src.utils.scrapers import scrape_url
except ImportError:
    from utils.parsers import parse_file
    from utils.scrapers import scrape_url


DEFAULT_RAW_DIR = Path("raw")


class RawCapture(BaseModel):
    """Pydantic schema representing a validated raw knowledge capture."""

    id: str = Field(..., description="Unique timestamped capture ID")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    source_type: Literal["text", "url", "file"] = Field(..., description="Ingestion source type")
    source_ref: str = Field(..., description="Original reference (e.g. filename, URL, or 'manual')")
    title: str = Field(..., description="Extracted or user-supplied title")
    raw_content: str = Field(..., description="Full text payload")
    content_hash: str = Field(..., description="SHA-256 fingerprint for deduplication")
    tags: List[str] = Field(default_factory=list, description="Initial optional user tags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extraction metadata & warnings")
    processed: bool = Field(default=False, description="Whether this capture has been organized into wiki/")


def generate_capture_id() -> str:
    """Generate a chronological and unique ID: YYYYMMDD-HHMMSS-<6-hex-chars>."""
    import uuid

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    return f"{now_str}-{rand_suffix}"


def compute_content_hash(text: str) -> str:
    """Calculate SHA-256 digest of normalized text."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_duplicate_capture(content_hash: str, raw_dir: Path) -> Optional[dict]:
    """Scan existing raw/ captures for matching SHA-256 hash."""
    if not raw_dir.exists():
        return None

    for item in raw_dir.glob("*.json"):
        try:
            with open(item, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("content_hash") == content_hash:
                    return data
        except Exception:
            continue
    return None


def list_raw_captures(raw_dir: Path = DEFAULT_RAW_DIR) -> List[dict]:
    """Return all stored captures ordered by timestamp."""
    if not raw_dir.exists():
        return []

    captures = []
    for item in sorted(raw_dir.glob("*.json")):
        try:
            with open(item, "r", encoding="utf-8") as f:
                captures.append(json.load(f))
        except Exception:
            continue
    return captures


def capture(
    text: Optional[str] = None,
    url: Optional[str] = None,
    file_path: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    raw_dir: Path = DEFAULT_RAW_DIR,
    force: bool = False,
) -> RawCapture:
    """
    Ingest a note, URL, or local document and persist to raw/ vault.
    Validates edge cases: empty strings, duplicates, scrapers, and file parsers.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    tags = tags or []

    # Mutually exclusive validation
    inputs_provided = [bool(text), bool(url), bool(file_path)]
    if sum(inputs_provided) != 1:
        raise ValueError("Must provide exactly ONE of: --text, --url, or --file.")

    source_type: Literal["text", "url", "file"]
    source_ref: str
    inferred_title: str
    raw_content: str
    metadata: dict[str, Any] = {}

    # 1. Plain Text Ingestion
    if text is not None:
        raw_content = text.strip()
        if not raw_content:
            raise ValueError("Cannot capture empty or whitespace-only text.")
        source_type = "text"
        source_ref = "manual"
        # Infer title from first line if not provided
        first_line = raw_content.split("\n")[0].strip("# ").strip()
        inferred_title = title.strip() if title else (first_line[:60] if first_line else "Quick Note")

    # 2. Web URL Ingestion
    elif url is not None:
        source_type = "url"
        source_ref = url.strip()
        scraped_title, scraped_content, scrape_meta = scrape_url(source_ref)
        raw_content = scraped_content
        metadata = scrape_meta
        inferred_title = title.strip() if title else scraped_title

    # 3. File Document Ingestion
    elif file_path is not None:
        clean_file_path = file_path.strip().strip("'\"")
        source_type = "file"
        source_ref = str(Path(clean_file_path).resolve())
        parsed_title, parsed_content, parse_meta = parse_file(clean_file_path)
        raw_content = parsed_content
        metadata = parse_meta
        inferred_title = title.strip() if title else parsed_title

    # Compute hash & check duplicates
    content_hash = compute_content_hash(raw_content)
    if not force:
        existing = find_duplicate_capture(content_hash, raw_dir)
        if existing:
            print(f"[!] Warning: Duplicate content detected! Already captured as '{existing.get('id')}'.")
            print(f"    Title: {existing.get('title')}")
            print(f"    Timestamp: {existing.get('timestamp')}")
            print(f"    (Use --force to capture duplicate anyway)")
            return RawCapture(**existing)

    # Build Pydantic capture model
    capture_id = generate_capture_id()
    now_utc = datetime.now(timezone.utc).isoformat()

    record = RawCapture(
        id=capture_id,
        timestamp=now_utc,
        source_type=source_type,
        source_ref=source_ref,
        title=inferred_title,
        raw_content=raw_content,
        content_hash=content_hash,
        tags=tags,
        metadata=metadata,
        processed=False,
    )

    # Atomic write to raw/{id}.json
    target_file = raw_dir / f"{capture_id}.json"
    temp_file = raw_dir / f"{capture_id}.tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(record.model_dump(), f, indent=2, ensure_ascii=False)
    temp_file.replace(target_file)

    return record


def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="SecondSelf: One-command knowledge capture engine (The Archivist)."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-t", "--text", type=str, help="Quick note or text string to capture.")
    group.add_argument("-u", "--url", type=str, help="Web URL / article link to scrape and capture.")
    group.add_argument("-f", "--file", type=str, help="Local file path (.pdf, .txt, .md) to capture.")
    group.add_argument("-l", "--list", action="store_true", help="List all captured items in raw/.")

    parser.add_argument("--title", type=str, default=None, help="Custom title for the capture.")
    parser.add_argument("--tags", type=str, default=None, help="Comma-separated tags (e.g. 'ai,python,ideas').")
    parser.add_argument("--force", action="store_true", help="Force capture even if content is duplicate.")
    parser.add_argument("--dir", type=str, default="raw", help="Target directory for raw captures (default: raw).")

    args = parser.parse_args()
    raw_dir = Path(args.dir)

    # Handle listing
    if args.list:
        captures = list_raw_captures(raw_dir)
        if not captures:
            print("No items captured yet in raw/ vault.")
            return

        print(f"\n{'='*75}")
        print(f" SecondSelf Vault: {len(captures)} Raw Captures")
        print(f"{'='*75}")
        print(f"{'ID':<25} | {'TYPE':<6} | {'PROCESSED':<9} | {'TITLE'}")
        print(f"{'-'*75}")
        for c in captures:
            proc_status = "[DONE]" if c.get("processed") else "[NEW]"
            title_preview = (c.get("title") or "Untitled")[:32]
            print(f"{c['id']:<25} | {c['source_type']:<6} | {proc_status:<9} | {title_preview}")
        print(f"{'='*75}\n")
        return

    # Handle no args -> Interactive prompt
    if not (args.text or args.url or args.file):
        print("\n--- SecondSelf: Fast Ingestion ---")
        print("Select capture type:")
        print("1) Quick Text Note")
        print("2) Web URL")
        print("3) File Path (.txt, .md, .pdf)")
        choice = input("Enter choice (1-3): ").strip()
        if choice == "1":
            args.text = input("Enter note content: ").strip()
        elif choice == "2":
            args.url = input("Enter web URL: ").strip().strip("'\"")
        elif choice == "3":
            args.file = input("Enter file path: ").strip().strip("'\"")
        else:
            print("Invalid selection. Exiting.")
            sys.exit(1)

    parsed_tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    try:
        rec = capture(
            text=args.text,
            url=args.url,
            file_path=args.file,
            title=args.title,
            tags=parsed_tags,
            raw_dir=raw_dir,
            force=args.force,
        )

        print("\n" + "=" * 60)
        print(" [OK] Capture Ingested Successfully!")
        print("=" * 60)
        print(f"ID:          {rec.id}")
        print(f"Timestamp:   {rec.timestamp}")
        print(f"Type:        {rec.source_type}")
        print(f"Title:       {rec.title}")
        print(f"Source Ref:  {rec.source_ref}")
        print(f"Length:      {len(rec.raw_content)} chars")
        if rec.tags:
            print(f"Tags:        {', '.join(rec.tags)}")
        if rec.metadata.get("warnings"):
            print(f"Warnings:    {rec.metadata['warnings']}")
        print(f"Saved To:    {raw_dir / (rec.id + '.json')}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
