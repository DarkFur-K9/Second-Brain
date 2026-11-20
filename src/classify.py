"""SecondSelf: PARA Auto-Classification Engine (The Librarian - Task 2.1).

Classifies raw captures into the PARA methodology (Projects, Areas, Resources, Archives),
generates tags, summaries, and structured Markdown notes with YAML frontmatter.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

DEFAULT_RAW_DIR = Path("raw")
DEFAULT_WIKI_DIR = Path("wiki")

PARA_CATEGORIES = ("Projects", "Areas", "Resources", "Archives")
ParaCategory = Literal["Projects", "Areas", "Resources", "Archives"]


class ClassificationResult(BaseModel):
    """Structured LLM classification output schema."""

    title: str = Field(..., description="Clean, professional title for the note")
    category: ParaCategory = Field(
        ..., description="PARA framework category (Projects, Areas, Resources, Archives)"
    )
    tags: List[str] = Field(
        default_factory=list, description="3-5 lowercase semantic tags"
    )
    summary: str = Field(..., description="1-2 sentence distillation of core knowledge")
    clean_markdown: str = Field(
        ..., description="Curated markdown content with headings and bullet points"
    )


def safe_slug(title: str) -> str:
    """
    Generate a clean, filesystem-safe filename slug.
    Prevents Windows-illegal characters (: * ? " < > | / \\) and caps length.
    """
    clean = re.sub(r'[\\/:*?"<>|]', "", title)
    clean = re.sub(r"[\s_]+", "-", clean.strip().lower())
    clean = re.sub(r"[^\w\-]", "", clean)
    clean = re.sub(r"-+", "-", clean).strip("-")
    return (clean[:60] if clean else "untitled").strip()


def build_system_prompt() -> str:
    """Prompt enforcing Tiago Forte's PARA framework and JSON schema."""
    return """You are the Librarian of SecondSelf, an autonomous personal AI second brain.
Your job is to read an unorganized raw capture and organize it using Tiago Forte's PARA framework.

Categories:
1. "Projects": Active efforts with a specific goal and a definite deadline/completion state (e.g. building a specific app, preparing a presentation, writing a specific report).
2. "Areas": Ongoing spheres of activity and standards to maintain over time with NO end date (e.g. Health, Personal Finance, Habits, System Architecture, Deep Work, Career).
3. "Resources": Reference materials, guides, topics of ongoing interest, cheatsheets, research, book notes, tools, and bookmarks you may want to look up later.
4. "Archives": Inactive or completed items from the other three categories preserved for historical context.

Rules:
- Output MUST be valid JSON adhering to the specified schema.
- "title": Clean, concise title (4-8 words).
- "category": Must be exactly one of: "Projects", "Areas", "Resources", "Archives".
- "tags": 3 to 5 relevant lowercase tags (alphanumeric and hyphens only).
- "summary": 1 to 2 crisp sentences summarizing the essential takeaways.
- "clean_markdown": The content reformatted into clean, structured Markdown with relevant headers (H2, H3), bullet points, and code blocks if applicable. Strip out web boilerplate/advertisements. If the raw content was very short, keep it brief without making up fake information.
- If the content is in a foreign language, write the tags and summary in English, but preserve the main content in its original language.
"""


def get_groq_client():
    """Initialize Groq client with API key from environment."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found in environment or .env file. "
            "Please obtain a free key at https://console.groq.com and set GROQ_API_KEY in .env."
        )
    from groq import Groq

    return Groq(api_key=api_key)


def get_best_model(client, preferred: Optional[str] = None) -> str:
    """Select the best available model on the connected Groq account."""
    if preferred:
        return preferred
    env_model = os.getenv("GROQ_MODEL")
    if env_model:
        return env_model

    try:
        available = [m.id for m in client.models.list().data]
        preferences = [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ]
        for pref in preferences:
            if pref in available:
                return pref
        candidates = [
            m for m in available
            if not any(x in m.lower() for x in ["whisper", "guard", "audio"])
        ]
        if candidates:
            return candidates[0]
    except Exception:
        pass
    return "qwen/qwen3.8-27b"


def classify_with_llm(
    title: str,
    raw_content: str,
    source_type: str,
    source_ref: str,
    model: Optional[str] = None,
    max_retries: int = 3,
) -> ClassificationResult:
    """
    Call Groq API with structured JSON output and exponential backoff retry.
    Falls back gracefully if API is unavailable or limits hit.
    """
    client = get_groq_client()
    selected_model = get_best_model(client, preferred=model)

    # Protect against context window exhaustion for massive raw captures
    truncated_content = raw_content[:14000]
    if len(raw_content) > 14000:
        truncated_content += (
            f"\n\n[... Note: Content truncated for classification. Original length: {len(raw_content)} chars ...]"
        )

    user_payload = {
        "original_title": title,
        "source_type": source_type,
        "source_ref": source_ref,
        "content": truncated_content,
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {
                        "role": "user",
                        "content": f"Organize and classify this capture into JSON:\n\n{json.dumps(user_payload, ensure_ascii=False)}",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=900,
            )

            raw_json = response.choices[0].message.content
            parsed = json.loads(raw_json)

            # Enforce valid category
            cat = parsed.get("category", "").capitalize()
            if cat not in PARA_CATEGORIES:
                # Default heuristic based on keywords
                cat = "Resources"

            # Clean tags
            clean_tags = [
                re.sub(r"[^\w\-]", "", str(t).lower())
                for t in parsed.get("tags", [])
                if str(t).strip()
            ]

            return ClassificationResult(
                title=parsed.get("title") or title or "Untitled Note",
                category=cat,  # type: ignore
                tags=clean_tags or ["general"],
                summary=parsed.get("summary")
                or raw_content[:150].replace("\n", " ").strip(),
                clean_markdown=parsed.get("clean_markdown") or raw_content,
            )

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "model_not_found" in err_str or "does not exist" in err_str:
                selected_model = get_best_model(client)
            elif "rate_limit" in err_str or "429" in err_str or "503" in err_str:
                selected_model = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
            wait_time = 2**attempt
            print(f"    [!] Groq API attempt {attempt + 1} failed ({e}). Retrying in {wait_time}s...")
            time.sleep(wait_time)

    # If all retries fail, return safe fallback classification without crashing
    print(f"    [!] Falling back to heuristic classification due to API error: {last_error}")
    fallback_title = title if title else "Quick Note"
    return ClassificationResult(
        title=fallback_title,
        category="Resources",
        tags=["unclassified"],
        summary=raw_content[:150].replace("\n", " ").strip() + "...",
        clean_markdown=raw_content,
    )


def format_markdown_note(
    record: Dict[str, Any],
    classification: ClassificationResult,
) -> str:
    """Format structured Markdown note with standardized YAML frontmatter."""
    tags_yaml = "\n".join(f'  - "{t}"' for t in classification.tags)
    
    # Escape quotes in summary and title for YAML safety
    safe_title = classification.title.replace('"', '\\"')
    safe_summary = classification.summary.replace('"', '\\"').replace("\n", " ")

    frontmatter = f"""---
id: "{record.get('id', '')}"
title: "{safe_title}"
para_category: "{classification.category}"
tags:
{tags_yaml}
summary: "{safe_summary}"
created_at: "{record.get('timestamp', '')}"
source_type: "{record.get('source_type', 'text')}"
source_ref: "{record.get('source_ref', 'manual')}"
links: []
---

# {classification.title}

{classification.clean_markdown.strip()}

## Related Notes
*(Semantic auto-linking will connect related notes here)*
"""
    return frontmatter


def save_wiki_note(
    record: Dict[str, Any],
    classification: ClassificationResult,
    wiki_dir: Path = DEFAULT_WIKI_DIR,
) -> Path:
    """
    Save the classified note into wiki/{category}/{slug}.md.
    Handles filename collisions gracefully.
    """
    category_dir = wiki_dir / classification.category
    category_dir.mkdir(parents=True, exist_ok=True)

    base_slug = safe_slug(classification.title)
    target_path = category_dir / f"{base_slug}.md"

    # Collision defense: if a note with this slug exists with a DIFFERENT id, append short id
    if target_path.exists():
        try:
            content = target_path.read_text(encoding="utf-8")
            if f'id: "{record.get("id")}"' not in content:
                short_id = record.get("id", "000000").split("-")[-1]
                target_path = category_dir / f"{base_slug}-{short_id}.md"
        except Exception:
            pass

    note_content = format_markdown_note(record, classification)
    target_path.write_text(note_content, encoding="utf-8")
    return target_path


def mark_raw_processed(raw_file: Path) -> None:
    """Set processed: true in the raw capture JSON file."""
    try:
        data = json.loads(raw_file.read_text(encoding="utf-8"))
        data["processed"] = True
        temp_file = raw_file.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temp_file.replace(raw_file)
    except Exception as e:
        print(f"    [!] Failed to update processed flag in {raw_file.name}: {e}")


def process_capture_file(
    raw_file: Path,
    wiki_dir: Path = DEFAULT_WIKI_DIR,
    model: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[Tuple[ClassificationResult, Path]]:
    """Process a single raw capture file through the PARA classification pipeline."""
    try:
        record = json.loads(raw_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] Error reading {raw_file.name}: {e}")
        return None

    raw_id = record.get("id", raw_file.stem)
    title = record.get("title", "Untitled")
    raw_content = record.get("raw_content", "")
    source_type = record.get("source_type", "text")
    source_ref = record.get("source_ref", "manual")

    if not raw_content.strip():
        print(f"[-] Skipping empty capture: {raw_id}")
        return None

    print(f"\n[+] Classifying: {raw_id} | Title: '{title[:40]}'")
    classification = classify_with_llm(
        title=title,
        raw_content=raw_content,
        source_type=source_type,
        source_ref=source_ref,
        model=model,
    )

    print(f"    -> Category: {classification.category}")
    print(f"    -> Tags:     {', '.join(classification.tags)}")
    print(f"    -> Summary:  {classification.summary[:75]}...")

    if dry_run:
        print("    [Dry Run] Note not written to disk.")
        return classification, Path("dry_run.md")

    target_path = save_wiki_note(record, classification, wiki_dir)
    mark_raw_processed(raw_file)
    print(f"    -> Saved to: {target_path}")

    return classification, target_path


def classify_all(
    raw_dir: Path = DEFAULT_RAW_DIR,
    wiki_dir: Path = DEFAULT_WIKI_DIR,
    force: bool = False,
    model: Optional[str] = None,
    dry_run: bool = False,
) -> List[Tuple[ClassificationResult, Path]]:
    """Scan raw/ and classify all unprocessed items."""
    if not raw_dir.exists():
        print(f"[!] Raw directory not found: {raw_dir}")
        return []

    raw_files = sorted(raw_dir.glob("*.json"))
    if not raw_files:
        print("[i] No captures found in raw/ vault.")
        return []

    to_process = []
    for rf in raw_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            if force or not data.get("processed", False):
                to_process.append(rf)
        except Exception:
            continue

    print(f"\n{'='*65}")
    print(f" SecondSelf: PARA Classification Pipeline (The Librarian)")
    print(f"{'='*65}")
    print(f"Total raw items:       {len(raw_files)}")
    print(f"Unprocessed to file:   {len(to_process)}")
    print(f"Target wiki vault:     {wiki_dir.resolve()}")
    print(f"{'='*65}")

    if not to_process:
        print("All items in raw/ are already classified! Use --force to re-classify.")
        return []

    results = []
    for idx, rf in enumerate(to_process, 1):
        print(f"\n[{idx}/{len(to_process)}]", end="")
        res = process_capture_file(rf, wiki_dir=wiki_dir, model=model, dry_run=dry_run)
        if res:
            results.append(res)
        # Gentle rate limit pacing between calls
        time.sleep(0.5)

    print(f"\n{'='*65}")
    print(f" [OK] Successfully organized {len(results)} note(s) into wiki/")
    print(f"{'='*65}\n")
    return results


def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="SecondSelf: PARA Auto-Classification Pipeline (The Librarian)."
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Classify a specific raw capture ID (e.g. 20261116-113505-b2ce2b).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all pending/unprocessed captures in raw/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-classify notes even if already marked as processed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run classification and show results without writing to wiki/.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Custom Groq model (e.g. llama-3.3-70b-versatile or llama-3.1-8b-instant).",
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="raw",
        help="Source directory for raw captures (default: raw).",
    )
    parser.add_argument(
        "--wiki-dir",
        type=str,
        default="wiki",
        help="Target directory for organized wiki (default: wiki).",
    )

    args = parser.parse_args()
    raw_dir = Path(args.raw_dir)
    wiki_dir = Path(args.wiki_dir)

    if args.id:
        target_file = raw_dir / f"{args.id}.json"
        if not target_file.exists():
            # Check without .json suffix if user provided full filename
            target_file = raw_dir / args.id
        if not target_file.exists():
            print(f"[ERROR] Capture file not found for ID: {args.id}", file=sys.stderr)
            sys.exit(1)
        process_capture_file(
            target_file, wiki_dir=wiki_dir, model=args.model, dry_run=args.dry_run
        )
    else:
        # Default behavior: process all pending captures
        classify_all(
            raw_dir=raw_dir,
            wiki_dir=wiki_dir,
            force=args.force,
            model=args.model,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
