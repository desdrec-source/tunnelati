#!/usr/bin/env python3
"""Tunnelati bot — scan accounts, or force one post with --post-id."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    LIVE_MODE,
    WEBSITE_ARTICLES_DIR,
    ARTICLES_OUT,
    PROCESSED_PATH,
    validate_required,
)
from utils.logger import get_logger
from utils.state import ProcessedStore
from monitors.x_monitor import XMonitor
from generators.content_generator import ContentGenerator

logger = get_logger("main")


def _id_from_arg(value: str) -> str:
    value = value.strip()
    m = re.search(r"status/(\d+)", value)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d+", value):
        return value
    raise argparse.ArgumentTypeError(f"Not a post id or status URL: {value}")


def process_posts(posts, store, force: bool = False) -> int:
    if not posts:
        logger.info("No posts to process.")
        return 0

    if not force:
        new_posts = [p for p in posts if not store.has(p["id"])]
        skipped = len(posts) - len(new_posts)
        if skipped:
            logger.info("Skipping %d already-processed post(s)", skipped)
        posts = new_posts

    if not posts:
        logger.info("Nothing new to process. Exiting quietly.")
        return 0

    generator = ContentGenerator()
    success = 0
    for item in posts:
        logger.info("Processing @%s — %s", item["author"], item["id"])
        generated = generator.generate(item)
        if not generated:
            logger.warning("Skipping post %s (generation failed)", item["id"])
            continue
        path = generator.write_files(
            item,
            generated,
            live=LIVE_MODE,
            website_dir=WEBSITE_ARTICLES_DIR if LIVE_MODE else None,
        )
        if path:
            store.mark(
                item["id"],
                url=item.get("url"),
                author=item.get("author"),
                title=generated.get("title"),
            )
            success += 1

    logger.info("Done. Generated content for %d / %d post(s).", success, len(posts))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tunnelati high-signal bot")
    parser.add_argument("--post-id", type=_id_from_arg, help="Status id or x.com status URL")
    parser.add_argument("--force", action="store_true", help="Reprocess even if already known")
    args = parser.parse_args(argv)

    logger.info("=== Tunnelati bot starting ===")
    logger.info("Mode: %s", "LIVE" if LIVE_MODE else "DRY-RUN (safe)")

    missing = validate_required()
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        return 1

    store = ProcessedStore(PROCESSED_PATH)
    store.seed_from_articles(WEBSITE_ARTICLES_DIR)
    store.seed_from_articles(ARTICLES_OUT)

    monitor = XMonitor()

    if args.post_id:
        logger.info("Force path: single post %s", args.post_id)
        if not hasattr(monitor, "fetch_tweet_by_id"):
            logger.error("x_monitor.py is missing fetch_tweet_by_id — update the monitor file")
            return 1
        item = monitor.fetch_tweet_by_id(args.post_id)
        if not item:
            logger.error("Could not load post %s", args.post_id)
            return 1
        return process_posts([item], store, force=True)

    posts = monitor.fetch_high_signal_posts()
    if not posts:
        logger.info("No high-signal posts found. Exiting quietly.")
        return 0
    return process_posts(posts, store, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())