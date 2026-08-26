# Tunnelati bot - Phase 1
# Dry-run by default. Never publishes without LIVE_MODE=true and human review.

import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LIVE_MODE = os.getenv("LIVE_MODE", "false").lower() == "true"
PROCESSED_FILE = Path(__file__).parent / "processed.json"
CONTENT_DIR = Path(__file__).parent.parent / "website" / "src" / "content" / "articles"

def load_processed():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_processed(processed):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(processed)), f, indent=2)

def make_slug(title):
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:80]

def generate_markdown(item):
    frontmatter = f"""---
title: "{item['title']}"
description: "{item['description']}"
pubDate: {item['pubDate']}
category: "{item['category']}"
featured: false
hasVideo: {str(item.get('hasVideo', False)).lower()}
sourceUrl: "{item['sourceUrl']}"
sourceName: "{item['sourceName']}"
---

{item['body']}
"""
    return frontmatter

def run_dry_run():
    print("=== Tunnelati Bot - DRY RUN ===")
    print(f"LIVE_MODE = {LIVE_MODE}")
    print(f"Content folder: {CONTENT_DIR}")
    print()

    sample_items = [
        {
            "id": "demo-2026-08-25-vegas",
            "title": "Clark County approves 19 additional Vegas Loop stations - total entitled now 123",
            "description": "Official confirmation from The Boring Company that Clark County approved 19 more stations.",
            "pubDate": "2026-08-25",
            "category": "Vegas Loop",
            "sourceUrl": "https://x.com/boringcompany/status/2092396130361606374",
            "sourceName": "The Boring Company (@boringcompany)",
            "body": "On 25 August 2026 The Boring Company posted that Clark County had approved an additional 19 Vegas Loop stations, bringing the entitled total to 123.",
            "hasVideo": False,
        }
    ]

    processed = load_processed()
    new_count = 0

    for item in sample_items:
        if item["id"] in processed:
            print(f"SKIP (already processed): {item['id']}")
            continue

        md = generate_markdown(item)
        slug = make_slug(item["title"])
        filename = f"{slug}.md"
        target = CONTENT_DIR / filename

        print(f"WOULD CREATE: {target}")
        print("--- draft start ---")
        print(md[:400] + "..." if len(md) > 400 else md)
        print("--- draft end ---")
        print()

        if LIVE_MODE:
            CONTENT_DIR.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"WROTE FILE: {target}")
        else:
            print("(dry-run - no file written)")

        processed.add(item["id"])
        new_count += 1

    if new_count > 0:
        save_processed(processed)
        print(f"Updated processed.json with {new_count} new id(s)")
    else:
        print("No new items.")

    print()
    print("Done. Always review drafts before setting LIVE_MODE=true.")

if __name__ == "__main__":
    run_dry_run()
