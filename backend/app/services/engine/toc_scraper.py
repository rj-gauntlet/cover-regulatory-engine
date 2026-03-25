"""Scrape and cache the LAMC Article 2 Table of Contents.

Provides dynamic zone_class → LAMC section/URL mapping by scraping the
amlegal.com TOC page, eliminating the need for a hardcoded dictionary.
"""
import hashlib
import logging
import re
import uuid

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import TocEntry

logger = logging.getLogger(__name__)

TOC_URL = "https://codelibrary.amlegal.com/codes/los_angeles/latest/lapz/0-0-0-704"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Regex to extract zone class from TOC entry titles like:
#   SEC. 12.12.2. "CR" LIMITED COMMERCIAL ZONE.
#   SEC. 12.08.1. RU RESIDENTIAL URBAN ZONE.
# Captures: section_number, zone_class (quoted or unquoted), title
_ZONE_SECTION_RE = re.compile(
    r"SEC\.\s+"
    r"(12\.\d[\d.]*)\.\s+"          # section number (e.g. 12.12.2)
    r'(?:["\u201c]([A-Z][A-Z0-9.]*)["\u201d]\s+)?'  # optional quoted zone code
    r"([A-Z].*?)\.?\s*$",           # title text
    re.IGNORECASE,
)

# For entries without quotes, extract leading zone code from title
_UNQUOTED_ZONE_RE = re.compile(r"^([A-Z][A-Z0-9-]*(?:\([A-Z]+\))?)\s+")

# Zone classes that represent actual zoning designations (not general provisions)
_ZONE_KEYWORDS = {
    "OS", "PF", "A1", "A2", "RA", "RE", "RS", "R1", "R2", "R3", "R4", "R5",
    "RU", "RZ", "RW1", "RW2", "RD", "RMP", "RAS3", "RAS4",
    "P", "PB", "CR", "C1", "C1.5", "C2", "C4", "C5", "CW", "CM",
    "MR1", "MR2", "M1", "M2", "M3",
    "ADP", "LASED", "CEC", "PVSP", "DNSP", "CCS", "LAX", "SL", "HP",
    "USC-1A", "USC-1B", "USC-2", "USC-3", "WC", "CM(GM)",
}


async def scrape_toc() -> tuple[str, dict[str, dict]]:
    """Fetch the LAMC Article 2 TOC page and parse zone section entries.

    Returns:
        (content_hash, {zone_class: {"section": ..., "title": ..., "url_path": ...}})
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(TOC_URL, headers=HEADERS)
        response.raise_for_status()

    content_hash = hashlib.sha256(response.text.encode()).hexdigest()

    soup = BeautifulSoup(response.text, "html.parser")

    entries: dict[str, dict] = {}

    # Parse all links that point to LAMC sections
    for link in soup.find_all("a", href=re.compile(r"/lapz/0-0-0-\d+")):
        text = link.get_text(strip=True)
        href = link["href"]

        match = _ZONE_SECTION_RE.match(text)
        if not match:
            continue

        section_number = match.group(1)
        zone_class = match.group(2)  # from quoted pattern
        title = match.group(3).strip()

        # If no quoted zone code, try to extract from title
        if not zone_class:
            unquoted = _UNQUOTED_ZONE_RE.match(title)
            if unquoted:
                zone_class = unquoted.group(1)

        if not zone_class:
            continue

        zone_class = zone_class.upper()

        # Only include known zone designations
        if zone_class not in _ZONE_KEYWORDS:
            continue

        # Extract just the /lapz/... path
        url_path = href
        if "/codes/" in href:
            url_path = "/" + href.split("/latest")[-1].lstrip("/")

        # Skip duplicates — keep first occurrence
        if zone_class not in entries:
            entries[zone_class] = {
                "section": section_number,
                "title": title,
                "url_path": url_path,
            }

    logger.info(f"Parsed {len(entries)} zone entries from TOC (hash: {content_hash[:12]}...)")
    return content_hash, entries


async def get_toc_hash(db: AsyncSession) -> str | None:
    """Get the content hash of the currently cached TOC, or None if not cached."""
    result = await db.execute(
        select(TocEntry.toc_content_hash).limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def save_toc(db: AsyncSession, content_hash: str, entries: dict[str, dict]) -> int:
    """Replace all cached TOC entries with new ones.

    Returns the number of entries saved.
    """
    await db.execute(delete(TocEntry))

    count = 0
    for zone_class, info in entries.items():
        entry = TocEntry(
            id=uuid.uuid4(),
            zone_class=zone_class,
            section_number=info["section"],
            title=info["title"],
            url_path=info["url_path"],
            toc_content_hash=content_hash,
        )
        db.add(entry)
        count += 1

    if count > 0:
        await db.flush()
        logger.info(f"Saved {count} TOC entries to database")

    return count


async def lookup_zone_in_toc(zone_class: str, db: AsyncSession) -> dict | None:
    """Look up a zone class in the cached TOC.

    Returns {"section": ..., "url": ..., "title": ...} or None.
    """
    result = await db.execute(
        select(TocEntry).where(TocEntry.zone_class == zone_class)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        return None

    return {
        "section": entry.section_number,
        "url": entry.url_path,
        "title": entry.title,
    }
