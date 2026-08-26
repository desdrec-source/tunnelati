"""
Generate short X post + Markdown article from a high-signal source post
using the xAI / Grok API.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from config import (
    XAI_API_KEY,
    XAI_BASE_URL,
    XAI_MODEL,
    ARTICLES_OUT,
    POSTS_OUT,
    IMAGES_OUT,
    WEBSITE_IMAGES_DIR,
)
from utils.media import download_source_image, download_official_og_image, extract_http_urls
from utils.logger import get_logger
from utils.filters import slugify

logger = get_logger("generator")

SYSTEM_PROMPT = """You are a precise news writer for Tunnelati, a focused site covering only Grok and xAI.

Core rules:
- Neutral, precise, useful.
- Lead with facts from the source post.
- Attribute every specific claim.
- No hype, no speculation, no invented details.
- Slightly witty only when it helps clarity.
- Prefer silence over padding: if the source is thin, keep the article short and honest.

Limited context allowed:
- You may briefly explain well-established public background (what The Boring Company is, project names like Vegas Loop and Music City Loop, machine names like Prufrock).
- You may place the announcement in the wider Grok product surface when that is public knowledge.
- Do NOT invent numbers, dates, pricing, feature lists, benchmarks, or future plans not in the source.

Required article structure (body_markdown must follow this):

1. Lead paragraph — what happened, when, who announced it.
2. A Markdown blockquote with a short pull-quote (1-3 lines) capturing the key claim from the source.
3. ## What was announced — bullets or short paragraphs of facts from the source.
4. ## Context — brief verified background so a reader understands the product; no invention.
5. ## Limits of this report — one short paragraph stating what is not claimed.
6. ## Source — clear attribution and the source URL.

Length:
- Real product/feature announcements: aim 250-400 words.
- Thin sources: stay short; still use the same structure, just less context.

Output format (strict JSON only, no markdown fences, no extra text):
{
  "x_post": "Short accurate post (1-3 sentences). Include the source link.",
  "title": "Clear factual headline, max ~70 characters",
  "description": "One-sentence summary for SEO/cards, max ~160 characters",
  "body_markdown": "Full article body in Markdown following the required structure above."
}
"""


class ContentGenerator:
    @staticmethod
    def _infer_category(item: dict[str, Any], title: str, body: str) -> str:
        text = f"{title} {body} {item.get('text', '')}".lower()
        if any(k in text for k in ("vegas loop", "vegas", "clark county", "las vegas")):
            return "Vegas Loop"
        if any(k in text for k in ("nashville", "music city", "music city loop", "bna")):
            return "Nashville"
        if any(k in text for k in ("prufrock", "tbm", "tunnel boring", "autonomous ring")):
            return "Machines"
        if any(k in text for k in ("dubai", "competition", "tunnel vision")):
            return "Projects"
        return "Company"
    def __init__(self):
        if not XAI_API_KEY:
            raise ValueError("XAI_API_KEY is required")
        self.client = OpenAI(
            api_key=XAI_API_KEY,
            base_url=XAI_BASE_URL,
        )
        self.model = XAI_MODEL

    def _build_user_prompt(self, item: dict[str, Any]) -> str:
        return f"""Primary source post (do not invent beyond this + allowed public context):

Author: @{item['author']}
Date: {item.get('created_at', 'unknown')}
URL: {item['url']}

Text:
\"\"\"
{item['text']}
\"\"\"

Write:
1) A short accurate X post (include the source URL)
2) A Markdown article using the REQUIRED structure:
   - Lead paragraph
   - Blockquote pull-quote from the source
   - ## What was announced
   - ## Context (allowed public background only)
   - ## Limits of this report
   - ## Source (with URL)

If the source is a real product/feature announcement, aim for 250-400 words.
If the source is thin, keep it short but still use the same structure.
Never invent details not supported by the source or well-established public product context.
"""

    def generate(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Call Grok API and return parsed {x_post, title, description, body_markdown}."""
        user_prompt = self._build_user_prompt(item)

        try:
            logger.info("Generating content for post %s …", item["id"])
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1800,
            )
            raw = response.choices[0].message.content or ""
            raw = raw.strip()

            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            data = json.loads(raw)

            required = ("x_post", "title", "description", "body_markdown")
            for key in required:
                if key not in data or not str(data[key]).strip():
                    logger.error("Missing or empty field in model response: %s", key)
                    return None

            body = str(data["body_markdown"]).strip()
            word_count = len(body.split())
            if word_count < 120:
                logger.warning(
                    "Generated article too thin (%d words) — skipping post %s",
                    word_count,
                    item["id"],
                )
                return None

            return data

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from model: %s\nRaw: %s", e, raw[:400])
            return None
        except Exception as e:
            logger.exception("Generation failed for %s: %s", item["id"], e)
            return None

    def write_files(
        self,
        item: dict[str, Any],
        generated: dict[str, Any],
        live: bool = False,
        website_dir: Path | None = None,
    ) -> Path | None:
        title = generated["title"]
        slug = slugify(title)
        date_str = (item.get("created_at") or datetime.now(timezone.utc).isoformat())[:10]
        filename = f"{date_str}-{slug}.md"
        image_basename = f"{date_str}-{slug}"
        slug = slugify(title)
        date_str = (item.get("created_at") or datetime.now(timezone.utc).isoformat())[:10]
        filename = f"{date_str}-{slug}.md"

        now = datetime.now(timezone.utc)
        pub_date = item.get("created_at") or now.isoformat()
        try:
            pub_date_short = pub_date[:10]
        except Exception:
            pub_date_short = now.strftime("%Y-%m-%d")

        source_name = f"@{item['author']} on X"
        source_url = item["url"]
        category = self._infer_category(item, title, generated["body_markdown"])

        image_lines = ""
        media_list = item.get("media") or []
        downloaded = None
        if media_list:
            image_basename = f"{date_str}-{slug}"
            downloaded = download_source_image(media_list, IMAGES_OUT, image_basename)

        if not downloaded:
            page_candidates = extract_http_urls(
                item.get("text") or "",
                generated.get("body_markdown") or "",
                source_url,
            )
            downloaded = download_official_og_image(
                page_candidates, IMAGES_OUT, image_basename
            )
            if downloaded:
                local_path, alt = downloaded
                public_name = local_path.name
                safe_alt = alt.replace('"', "'")
                image_lines = (
                    f'image: "/images/articles/{public_name}"\n'
                    f'imageAlt: "{safe_alt}"\n'
                )
                if live:
                    WEBSITE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                    dest = WEBSITE_IMAGES_DIR / public_name
                    dest.write_bytes(local_path.read_bytes())
                    logger.info("LIVE: copied image → %s", dest)

        frontmatter = f"""---
title: "{title.replace('"', "'")}"
description: "{generated['description'].replace('"', "'")}"
pubDate: {pub_date_short}
source: "{source_name}"
sourceUrl: "{source_url}"
author: "Tunnelati"
draft: false
category: "{category}"
{image_lines}---

"""
        body = generated["body_markdown"].strip()
        if source_url not in body:
            body += f"\n\n*Source: [{source_name}]({source_url})*"

        full_md = frontmatter + body + "\n"

        out_path = ARTICLES_OUT / filename
        out_path.write_text(full_md, encoding="utf-8")
        logger.info("Wrote article → %s", out_path)

        post_path = POSTS_OUT / f"{date_str}-{slug}.txt"
        post_path.write_text(generated["x_post"].strip() + "\n", encoding="utf-8")
        logger.info("Wrote X post  → %s", post_path)

        if live and website_dir:
            website_dir.mkdir(parents=True, exist_ok=True)
            live_path = website_dir / filename
            live_path.write_text(full_md, encoding="utf-8")
            logger.info("LIVE: also wrote → %s", live_path)

        return out_path
