"""SecondSelf: Vault Diagnostic & Health Check Tool.

Verifies:
1. Raw capture storage and processing state
2. Wiki notes structure, frontmatter, and PARA taxonomy
3. Wikilink integrity (dangling / phantom link detection)
4. Vector embedding cache synchronization
5. Groq API connectivity and active model status
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import yaml
from dotenv import load_dotenv

load_dotenv()


def check_raw_captures(raw_dir: Path = Path("raw")) -> dict:
    if not raw_dir.exists():
        return {"total": 0, "processed": 0, "unprocessed": 0}
    files = list(raw_dir.glob("*.json"))
    total = len(files)
    processed = 0
    unprocessed_ids = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("processed", False):
                processed += 1
            else:
                unprocessed_ids.append(f.stem)
        except Exception:
            unprocessed_ids.append(f.stem)
    return {
        "total": total,
        "processed": processed,
        "unprocessed": total - processed,
        "unprocessed_ids": unprocessed_ids,
    }


def check_wiki_notes(wiki_dir: Path = Path("wiki")) -> dict:
    categories = ["Projects", "Areas", "Resources", "Archives"]
    cat_counts = {c: 0 for c in categories}
    notes = {}
    broken_links = []
    wikilink_regex = re.compile(r"\[\[(.*?)\]\]")

    if not wiki_dir.exists():
        return {"total": 0, "categories": cat_counts, "broken_links": [], "notes": {}}

    all_md_files = list(wiki_dir.glob("*/*.md"))
    known_slugs = {f.stem: f for f in all_md_files}

    for f in all_md_files:
        cat = f.parent.name
        if cat in cat_counts:
            cat_counts[cat] += 1

        content = f.read_text(encoding="utf-8")
        frontmatter = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass

        # Strip code blocks and inline code backticks before checking wikilinks
        clean_content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        clean_content = re.sub(r"`.*?`", "", clean_content)

        # Check links
        links = wikilink_regex.findall(clean_content)
        for link in links:
            target_slug = link.strip().lower().replace(" ", "-")
            # Normalize target
            if target_slug not in known_slugs and link not in known_slugs:
                broken_links.append({"from": f.stem, "target": link})

        notes[f.stem] = {
            "path": f,
            "category": cat,
            "title": frontmatter.get("title", f.stem),
            "tags": frontmatter.get("tags", []),
            "links_count": len(links),
        }

    return {
        "total": len(all_md_files),
        "categories": cat_counts,
        "broken_links": broken_links,
        "notes": notes,
    }


def check_embedding_cache(wiki_dir: Path = Path("wiki"), cache_file: Path = Path("wiki/.embeddings.npz")) -> dict:
    if not cache_file.exists():
        return {"status": "missing", "cached_count": 0, "out_of_sync": []}

    try:
        from src.link import load_cached_embeddings, load_wiki_notes
        cached_hashes, _ = load_cached_embeddings(cache_file)
        notes = load_wiki_notes(wiki_dir)
    except Exception as e:
        return {"status": "error", "error": str(e), "cached_count": 0, "out_of_sync": []}

    out_of_sync = []
    # Normalize cached paths to match by filename or relative path
    cached_by_stem = {Path(p).stem: h for p, h in cached_hashes.items()}

    for note in notes:
        cached_h = cached_by_stem.get(note.slug)
        if cached_h is None:
            out_of_sync.append({"slug": note.slug, "reason": "missing from cache"})
        elif cached_h != note.content_hash:
            out_of_sync.append({"slug": note.slug, "reason": "content modified"})

    return {
        "status": "synced" if not out_of_sync else "out_of_sync",
        "cached_count": len(cached_hashes),
        "out_of_sync": out_of_sync,
    }


def check_groq_api() -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"connected": False, "reason": "Missing GROQ_API_KEY in .env"}

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        models = [m.id for m in client.models.list().data]
        return {"connected": True, "models_count": len(models), "models": models[:4]}
    except Exception as e:
        return {"connected": False, "reason": str(e)}


def main():
    print("=" * 65)
    print(" 🧠 SecondSelf: Vault Diagnostic & Health Check")
    print("=" * 65)

    # 1. Raw Ingestion Check
    print("\n📁 [1/4] Raw Capture Vault:")
    raw_status = check_raw_captures()
    print(f"   • Total raw captures:     {raw_status['total']}")
    print(f"   • Processed into wiki:    {raw_status['processed']}")
    if raw_status["unprocessed"] > 0:
        print(f"   ⚠️ Pending unclassified:  {raw_status['unprocessed']} (run `python classify.py --all`)")
    else:
        print("   ✅ All raw captures organized!")

    # 2. Wiki Vault & Links Check
    print("\n📚 [2/4] Wiki Knowledge Vault (PARA):")
    wiki_status = check_wiki_notes()
    print(f"   • Total notes:            {wiki_status['total']}")
    for cat, count in wiki_status["categories"].items():
        print(f"     - {cat:<10}: {count}")

    broken = wiki_status["broken_links"]
    if broken:
        print(f"   ⚠️ Broken wikilinks:       {len(broken)}")
        for b in broken[:3]:
            print(f"     • In '{b['from']}': [[{b['target']}]] not found")
    else:
        print("   ✅ Zero broken wikilinks detected!")

    # 3. Embedding Sync Check
    print("\n🧬 [3/4] Semantic Vector Embeddings:")
    emb_status = check_embedding_cache()
    print(f"   • Cached vectors:         {emb_status['cached_count']}")
    if emb_status["status"] == "synced":
        print("   ✅ Embedding cache is fully in sync with wiki notes!")
    else:
        print(f"   ⚠️ Out of sync items:     {len(emb_status.get('out_of_sync', []))} (run `python link.py`)")

    # 4. Groq API Check
    print("\n🌐 [4/4] Groq LLM API Status:")
    groq_status = check_groq_api()
    if groq_status["connected"]:
        print(f"   ✅ Connected! Available models ({groq_status['models_count']}):")
        for m in groq_status["models"]:
            print(f"     • {m}")
    else:
        print(f"   ❌ Connection failed: {groq_status['reason']}")

    print("\n" + "=" * 65)
    print(" Health check completed cleanly.")
    print("=" * 65)


if __name__ == "__main__":
    main()
