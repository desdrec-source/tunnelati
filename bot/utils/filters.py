"""High-signal filters — official Boring Company coverage. Still no invented facts."""

from __future__ import annotations

import re
from typing import Any

from config import HIGH_SIGNAL_KEYWORDS


ANNOUNCEMENT_PHRASES = [
    "now available", "is now live", "is now out", "just released",
    "we're releasing", "we are releasing", "announcing", "introducing",
    "launched", "launching", "available today", "available now",
    "public beta", "open beta", "rolling out", "now rolling out",
    "model release", "api update", "new model", "acquired", "acquisition",
    "partnership", "partnering", "joining", "update", "shipping",
]


def is_reply(post: dict[str, Any]) -> bool:
    ref = post.get("referenced_tweets") or []
    return any(r.get("type") == "replied_to" for r in ref)


def is_retweet(post: dict[str, Any]) -> bool:
    ref = post.get("referenced_tweets") or []
    return any(r.get("type") == "retweeted" for r in ref)


def contains_high_signal_keyword(text: str) -> bool:
    text_lower = text.lower()
    for kw in HIGH_SIGNAL_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    
    
    return False


def contains_announcement_phrase(text: str) -> bool:
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in ANNOUNCEMENT_PHRASES)


def has_enough_substance(text: str) -> bool:
    return len(text.strip()) >= 40


def is_high_signal(
    post: dict[str, Any],
    author_username: str | None = None,
    require_keyword_for_elon: bool = True,
) -> bool:
    text = (post.get("text") or "").strip()
    if not text:
        return False
    if is_retweet(post):
        return False

    username = (author_username or "").lower().lstrip("@")
    has_keyword = contains_high_signal_keyword(text)
    has_announcement = contains_announcement_phrase(text)

    if is_reply(post):
        if not has_keyword:
            return False
        return len(text) >= 60

    if not has_enough_substance(text):
        return False

    if username in ("boringcompany", "theboringcompany"):
        return has_keyword or has_announcement or len(text) >= 60

    if username in ("elonmusk", "elon"):
        return has_keyword

    return has_keyword


def slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:80].strip("-")