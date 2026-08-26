"""Download source-post media and official OG images for article images."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from utils.logger import get_logger

logger = get_logger("media")

MIN_WIDTH = 400
MIN_HEIGHT = 200
MIN_BYTES = 8_000
MAX_BYTES = 8_000_000
MIN_MEAN_BRIGHTNESS = 18

ALLOWED_OG_HOSTS = frozenset({"x.ai", "www.x.ai", "grok.x.ai"})

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def _extension_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _is_usable_candidate(m: dict[str, Any]) -> bool:
    """Accept photos and video/gif preview stills."""
    mtype = (m.get("type") or "").lower()
    url = (m.get("url") or "").strip()
    if not url:
        return False
    if mtype and mtype not in ("photo", "video", "animated_gif", ""):
        logger.info("Skipping unsupported media (type=%s)", mtype)
        return False
    w = m.get("width") or 0
    h = m.get("height") or 0
    if mtype == "photo" and w and h and (w < MIN_WIDTH or h < MIN_HEIGHT):
        logger.info("Skipping tiny media %sx%s", w, h)
        return False
    return True


def _mean_brightness(data: bytes) -> float | None:
    try:
        from PIL import Image
        import statistics

        img = Image.open(BytesIO(data)).convert("RGB")
        img.thumbnail((160, 160))
        pixels = list(img.getdata())
        if not pixels:
            return None
        vals = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels]
        return float(statistics.fmean(vals))
    except Exception as e:
        logger.debug("Brightness check skipped: %s", e)
        return None


def _save_image_bytes(
    data: bytes,
    dest_dir: Path,
    basename: str,
    source_url: str,
    content_type: str = "",
    alt: str = "",
) -> tuple[Path, str] | None:
    size = len(data)
    if size < MIN_BYTES:
        logger.info("Skipping small download (%d bytes)", size)
        return None
    if size > MAX_BYTES:
        logger.info("Skipping oversized download (%d bytes)", size)
        return None
    brightness = _mean_brightness(data)
    if brightness is not None and brightness < MIN_MEAN_BRIGHTNESS:
        logger.info("Skipping near-black media (mean brightness %.1f)", brightness)
        return None

    ext = _extension_from_url(source_url)
    ct = (content_type or "").lower()
    if "png" in ct:
        ext = ".png"
    elif "webp" in ct:
        ext = ".webp"
    elif "gif" in ct:
        ext = ".gif"

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{basename}{ext}"
    dest.write_bytes(data)
    logger.info("Saved image (%d bytes) → %s", size, dest)
    return dest, (alt or "").strip() or "Image from the source post"


def download_source_image(
    media_list: list[dict[str, Any]],
    dest_dir: Path,
    basename: str,
) -> tuple[Path, str] | None:
    if not media_list:
        return None
    candidates = [m for m in media_list if _is_usable_candidate(m)]
    if not candidates:
        logger.info("No usable source media after filters")
        return None
    for media in candidates:
        url = media["url"]
        try:
            logger.info("Downloading source media → %s", basename)
            resp = requests.get(url, timeout=45, headers={"User-Agent": "TunnelatiBot/0.1"})
            resp.raise_for_status()
            saved = _save_image_bytes(
                resp.content,
                dest_dir,
                basename,
                url,
                content_type=resp.headers.get("content-type", ""),
                alt=media.get("alt") or "Image from the source post",
            )
            if saved:
                return saved
        except Exception as e:
            logger.warning("Failed to download media from %s: %s", url[:80], e)
    return None


def extract_http_urls(*texts: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for text in texts:
        if not text:
            continue
        for match in URL_RE.findall(text):
            url = match.rstrip(".,;:)")
            if url not in seen:
                seen.add(url)
                out.append(url)
    return out


def _host_allowed(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    if host.startswith("www."):
        return host in ALLOWED_OG_HOSTS or host[4:] in ALLOWED_OG_HOSTS
    return host in ALLOWED_OG_HOSTS


def fetch_og_image_url(page_url: str) -> str | None:
    if not _host_allowed(page_url):
        return None
    try:
        logger.info("Fetching official page for OG image → %s", page_url[:80])
        resp = requests.get(
            page_url,
            timeout=30,
            headers={
                "User-Agent": "TunnelatiBot/0.1 (news; +https://www.Tunnelati.com)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        resp.raise_for_status()
        html = resp.text[:500_000]
        m = OG_IMAGE_RE.search(html) or OG_IMAGE_RE_ALT.search(html)
        if not m:
            return None
        og = urljoin(page_url, m.group(1).strip())
        return og if og.startswith("http") else None
    except Exception as e:
        logger.warning("OG fetch failed for %s: %s", page_url[:80], e)
        return None


def download_official_og_image(
    candidate_page_urls: list[str],
    dest_dir: Path,
    basename: str,
) -> tuple[Path, str] | None:
    for page_url in candidate_page_urls:
        if not _host_allowed(page_url):
            continue
        og_url = fetch_og_image_url(page_url)
        if not og_url:
            continue
        try:
            logger.info("Downloading official OG image → %s", og_url[:80])
            resp = requests.get(og_url, timeout=45, headers={"User-Agent": "TunnelatiBot/0.1"})
            resp.raise_for_status()
            saved = _save_image_bytes(
                resp.content,
                dest_dir,
                basename,
                og_url,
                content_type=resp.headers.get("content-type", ""),
                alt="Official image from xAI",
            )
            if saved:
                return saved
        except Exception as e:
            logger.warning("Failed to download OG image %s: %s", og_url[:80], e)
    return None