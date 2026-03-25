"""Auto-seed zone rules from LAMC when Layer 1 has no data for a zone class.

Flow: zone_class → TOC lookup → LAMC section URL → scrape HTML → parse text
→ LLM extract structured rules → save to zone_rules (is_verified=False).

The LAMC section mapping is dynamically scraped from the amlegal.com Article 2
Table of Contents, cached in the toc_entries table, and refreshed on cache miss
only when the TOC page content has changed.
"""
import json
import logging
import uuid

from bs4 import BeautifulSoup
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ZoneRule
from app.services.engine.toc_scraper import (
    lookup_zone_in_toc,
    scrape_toc,
    get_toc_hash,
    save_toc,
)
from app.services.llm.base import LLMService

logger = logging.getLogger(__name__)

BASE_URL = "https://codelibrary.amlegal.com/codes/los_angeles/latest"

EXTRACTION_PROMPT = """You are a zoning code expert. Extract structured development standards from this Los Angeles Municipal Code (LAMC) section for the **{zone_class}** zone.

Extract ONLY the rules that apply to this specific zone class. Return a JSON object with a "rules" array. Each rule must have:
- "parameter": one of: front_setback, side_setback, rear_setback, max_height, max_stories, max_far, min_lot_area, lot_area_per_unit, min_lot_width, max_lot_coverage, min_parking_spaces, adu_allowed, adu_max_size, guest_house_allowed
- "category": one of: setback, height, far, lot, density, parking, adu, coverage
- "base_value": numeric value (float)
- "unit": one of: ft, stories, ratio, sqft, spaces, boolean (use 1.0 for true, 0.0 for false)
- "applies_to": array like ["ALL"] or ["SFH"] or ["ADU"]
- "source_text": the exact quote from the regulation supporting this value
- "conditions": optional object with notes about conditions (e.g. {{"note": "may be reduced for narrow lots"}})

If the zone references another zone's standards (e.g. "same as R1"), extract the values that would apply.
For residential uses in commercial zones, extract the residential development standards.

Return ONLY valid JSON: {{"rules": [...]}}
If you cannot find clear rules, return {{"rules": []}}.

LAMC Section {section_number} — {title}:
{regulatory_text}"""

KNOWLEDGE_PROMPT = """You are a zoning code expert with deep knowledge of the Los Angeles Municipal Code (LAMC).

Based on your knowledge of LAMC Section {section_number} ({title}), extract the development standards for the **{zone_class}** zone.

Return a JSON object with a "rules" array. Each rule must have:
- "parameter": one of: front_setback, side_setback, rear_setback, max_height, max_stories, max_far, min_lot_area, lot_area_per_unit, min_lot_width, max_lot_coverage, min_parking_spaces, adu_allowed, adu_max_size, guest_house_allowed
- "category": one of: setback, height, far, lot, density, parking, adu, coverage
- "base_value": numeric value (float)
- "unit": one of: ft, stories, ratio, sqft, spaces, boolean (use 1.0 for true, 0.0 for false)
- "applies_to": array like ["ALL"] or ["SFH"] or ["ADU"]
- "source_text": a description of the regulation (e.g. "Per LAMC Sec. 12.11, the front yard shall be not less than 15 feet")
- "conditions": optional object with notes about conditions

If the zone references another zone's standards (e.g. "same as R1 zone"), use the values from that referenced zone.
For residential uses in commercial zones, provide the residential development standards.
Only include rules you are confident about. Return {{"rules": []}} if unsure.

Return ONLY valid JSON: {{"rules": [...]}}"""


async def _fetch_section_text(url_path: str) -> str | None:
    """Fetch and extract plain text from an LAMC section page."""
    url = f"{BASE_URL}{url_path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch LAMC section {url}: {e}")
            return None

    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.find("div", class_="chunk-content") or soup.find("article") or soup.body
    if not content:
        return None

    for tag in content.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    text = content.get_text(separator=" ", strip=True)
    if len(text) > 12000:
        text = text[:12000]
    return text


async def _resolve_section_info(zone_class: str, db: AsyncSession) -> dict | None:
    """Resolve zone_class to LAMC section info using the cached TOC.

    If the zone isn't in the cached TOC, re-scrapes the TOC page and retries
    only if the page content has changed.

    Returns {"section": ..., "url": ..., "title": ...} or None.
    """
    # 1. Try cached TOC
    section_info = await lookup_zone_in_toc(zone_class, db)
    if section_info:
        return section_info

    # 2. Cache miss — scrape the TOC page
    logger.info(f"Zone class {zone_class} not in cached TOC, scraping amlegal TOC...")
    try:
        new_hash, entries = await scrape_toc()
    except Exception as e:
        logger.error(f"Failed to scrape TOC: {e}")
        # TOC scrape failed (e.g. 403) — return None to trigger LLM fallback
        return None

    # 3. Check if TOC has changed since last scrape
    stored_hash = await get_toc_hash(db)
    if stored_hash == new_hash:
        logger.info(f"TOC unchanged (hash: {new_hash[:12]}...), zone class {zone_class} not in LAMC Article 2")
        return None

    # 4. TOC changed (or first scrape) — save and retry
    await save_toc(db, new_hash, entries)
    section_info = await lookup_zone_in_toc(zone_class, db)
    if not section_info:
        logger.warning(f"Zone class {zone_class} not found in updated TOC")
    return section_info


# Sentinel value indicating LLM knowledge fallback (no section URL available)
_LLM_FALLBACK = "llm_fallback"


async def auto_seed_zone_rules(
    zone_class: str,
    db: AsyncSession,
    llm: LLMService,
) -> int:
    """Fetch LAMC text for a zone class, extract rules via LLM, save to zone_rules.

    Returns the number of rules created.
    """
    # Check if rules already exist
    existing = await db.execute(
        select(ZoneRule).where(ZoneRule.zone_class == zone_class).limit(1)
    )
    if existing.scalar_one_or_none():
        logger.info(f"Zone rules already exist for {zone_class}, skipping auto-seed")
        return 0

    # Resolve zone class to LAMC section via TOC
    section_info = await _resolve_section_info(zone_class, db)

    if section_info:
        logger.info(f"Auto-seeding zone rules for {zone_class} from LAMC Sec. {section_info['section']}")

        # Try to scrape the actual section text
        regulatory_text = await _fetch_section_text(section_info["url"])

        if regulatory_text:
            prompt = EXTRACTION_PROMPT.format(
                zone_class=zone_class,
                section_number=section_info["section"],
                title=section_info["title"],
                regulatory_text=regulatory_text,
            )
            source_note = f"Auto-seeded from LAMC Sec. {section_info['section']} text via LLM extraction"
        else:
            logger.info(f"LAMC section fetch failed for {zone_class}, falling back to LLM knowledge")
            prompt = KNOWLEDGE_PROMPT.format(
                zone_class=zone_class,
                section_number=section_info["section"],
                title=section_info["title"],
            )
            source_note = f"Auto-seeded from LLM knowledge of LAMC Sec. {section_info['section']} (source text unavailable)"
    else:
        # TOC lookup failed entirely (scrape blocked or zone not in LAMC)
        # Fall back to LLM knowledge using just the zone class name
        logger.info(f"TOC unavailable for {zone_class}, falling back to LLM knowledge")
        prompt = KNOWLEDGE_PROMPT.format(
            zone_class=zone_class,
            section_number="unknown",
            title=f"{zone_class} Zone",
        )
        source_note = f"Auto-seeded from LLM knowledge of {zone_class} zone (TOC lookup unavailable)"

    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": "You extract structured zoning rules from municipal code text. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response)
        rules_data = parsed.get("rules", [])
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"LLM extraction failed for {zone_class}: {e}")
        return 0

    if not rules_data:
        logger.warning(f"LLM returned no rules for {zone_class}")
        return 0

    resolved_section = section_info["section"] if section_info else "unknown"

    count = 0
    for rule in rules_data:
        try:
            base_value = float(rule.get("base_value", 0))
        except (ValueError, TypeError):
            continue

        db_rule = ZoneRule(
            id=uuid.uuid4(),
            zone_class=zone_class,
            parameter=rule.get("parameter", "unknown"),
            category=rule.get("category", "other"),
            base_value=base_value,
            unit=rule.get("unit", ""),
            conditions=rule.get("conditions"),
            applies_to=rule.get("applies_to", ["ALL"]),
            section_number=resolved_section,
            source_text=rule.get("source_text", "Auto-extracted from LAMC"),
            is_verified=False,
            notes=source_note,
        )
        db.add(db_rule)
        count += 1

    if count > 0:
        await db.flush()
        logger.info(f"Auto-seeded {count} rules for zone class {zone_class}")

    return count
