"""
Processed-post memory for Tunnelati bot.
Stores post IDs already handled so re-runs do not regenerate the same articles.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger("state")

STATUS_ID_RE = re.compile(
    r"(?:x\.com|twitter\.com)/[^/]+/status/(\d+)",
    re.IGNORECASE,
)


class ProcessedStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {"version": 1, "posts": {}}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("posts"), dict):
                self._data = raw
            elif isinstance(raw, list):
                self._data = {
                    "version": 1,
                    "posts": {str(i): {"id": str(i)} for i in raw},
                }
        except Exception as e:
            logger.warning("Could not read state file %s: %s", self.path, e)

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def has(self, post_id: str) -> bool:
        return str(post_id) in self._data["posts"]

    def mark(
        self,
        post_id: str,
        *,
        url: str | None = None,
        author: str | None = None,
        title: str | None = None,
    ) -> None:
        pid = str(post_id)
        entry: dict[str, Any] = {
            "id": pid,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        if url:
            entry["url"] = url
        if author:
            entry["author"] = author
        if title:
            entry["title"] = title
        self._data["posts"][pid] = entry
        self.save()

    def known_ids(self) -> set[str]:
        return set(self._data["posts"].keys())

    def seed_from_articles(self, articles_dir: Path) -> int:
        if not articles_dir.exists():
            return 0
        added = 0
        for md in articles_dir.glob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
            except Exception:
                continue
            m = re.search(r'(?m)^sourceUrl:\s*["\']?(\S+?)["\']?\s*$', text)
            url = m.group(1) if m else ""
            ids = STATUS_ID_RE.findall(url) if url else STATUS_ID_RE.findall(text)
            for pid in ids:
                if not self.has(pid):
                    self.mark(pid, url=url or None, title=md.stem)
                    added += 1
        if added:
            logger.info("Seeded %d post ids from existing articles in %s", added, articles_dir)
        return added