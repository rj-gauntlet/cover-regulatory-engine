"""Auto-seed zone rules from LAMC when Layer 1 has no data for a zone class.

Flow: zone_class → LAMC section URL → scrape HTML → parse text → LLM extract
structured rules → save to zone_rules (is_verified=False).
"""
import json
import logging
import uuid

from bs4 import BeautifulSoup
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ZoneRule
from app.services.llm.base import LLMService

logger = logging.getLogger(__name__)

BASE_URL = "https://codelibrary.amlegal.com/codes/los_angeles/latest"

ZONE_CLASS_TO_SECTION: dict[str, dict] = {
    "A1": {"section": "12.05", "url": "/lapz/0-0-0-1971", "title": "A1 Agricultural Zone"},
    "A2": {"section": "12.06", "url": "/lapz/0-0-0-2011", "title": "A2 Agricultural Zone"},
    "RE": {"section": "12.07", "url": "/lapz/0-0-0-2021", "title": "RE Residential Estate Zone"},
    "RE9": {"section": "12.07", "url": "/lapz/0-0-0-2021", "title": "RE Residential Estate Zone"},
    "RE11": {"section": "12.07", "url": "/lapz/0-0-0-2021", "title": "RE Residential Estate Zone"},
    "RE15": {"section": "12.07", "url": "/lapz/0-0-0-2021", "title": "RE Residential Estate Zone"},
    "RE20": {"section": "12.07", "url": "/lapz/0-0-0-2021", "title": "RE Residential Estate Zone"},
    "RE40": {"section": "12.07", "url": "/lapz/0-0-0-2021", "title": "RE Residential Estate Zone"},
    "RS": {"section": "12.07.01", "url": "/lapz/0-0-0-2031", "title": "RS Suburban Zone"},
    "R1": {"section": "12.08", "url": "/lapz/0-0-0-2052", "title": "R1 One-Family Zone"},
    "RU": {"section": "12.08.5", "url": "/lapz/0-0-0-2081", "title": "RU Zone"},
    "R2": {"section": "12.09", "url": "/lapz/0-0-0-2091", "title": "R2 Two-Family Zone"},
    "RD": {"section": "12.09.5", "url": "/lapz/0-0-0-2111", "title": "RD Restricted Density Zone"},
    "RD1.5": {"section": "12.09.5", "url": "/lapz/0-0-0-2111", "title": "RD Restricted Density Zone"},
    "RD2": {"section": "12.09.5", "url": "/lapz/0-0-0-2111", "title": "RD Restricted Density Zone"},
    "RD3": {"section": "12.09.5", "url": "/lapz/0-0-0-2111", "title": "RD Restricted Density Zone"},
    "R3": {"section": "12.10", "url": "/lapz/0-0-0-2131", "title": "R3 Multiple Dwelling Zone"},
    "R4": {"section": "12.11", "url": "/lapz/0-0-0-2161", "title": "R4 Multiple Dwelling Zone"},
    "R5": {"section": "12.11.5", "url": "/lapz/0-0-0-2191", "title": "R5 Multiple Dwelling Zone"},
    "C1": {"section": "12.12", "url": "/lapz/0-0-0-2201", "title": "C1 Limited Commercial Zone"},
    "C1.5": {"section": "12.12.5", "url": "/lapz/0-0-0-2221", "title": "C1.5 Limited Commercial Zone"},
    "C2": {"section": "12.13", "url": "/lapz/0-0-0-2241", "title": "C2 Commercial Zone"},
    "C4": {"section": "12.14", "url": "/lapz/0-0-0-2271", "title": "C4 Commercial Zone"},
    "C5": {"section": "12.14.5", "url": "/lapz/0-0-0-2291", "title": "C5 Commercial Zone"},
    "CM": {"section": "12.16", "url": "/lapz/0-0-0-2321", "title": "CM Commercial Manufacturing Zone"},
    "M1": {"section": "12.17", "url": "/lapz/0-0-0-2341", "title": "M1 Limited Industrial Zone"},
    "M2": {"section": "12.18", "url": "/lapz/0-0-0-2351", "title": "M2 Light Industrial Zone"},
    "M3": {"section": "12.19", "url": "/lapz/0-0-0-2361", "title": "M3 Heavy Industrial Zone"},
    "PF": {"section": "12.04.09", "url": "/lapz/0-0-0-1951", "title": "PF Public Facilities Zone"},
    "OS": {"section": "12.04.05", "url": "/lapz/0-0-0-1951", "title": "OS Open Space Zone"},
}

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


async def auto_seed_zone_rules(
    zone_class: str,
    db: AsyncSession,
    llm: LLMService,
) -> int:
    """Fetch LAMC text for a zone class, extract rules via LLM, save to zone_rules.

    Returns the number of rules created.
    """
    section_info = ZONE_CLASS_TO_SECTION.get(zone_class)
    if not section_info:
        logger.warning(f"No LAMC section mapping for zone class: {zone_class}")
        return 0

    existing = await db.execute(
        select(ZoneRule).where(ZoneRule.zone_class == zone_class).limit(1)
    )
    if existing.scalar_one_or_none():
        logger.info(f"Zone rules already exist for {zone_class}, skipping auto-seed")
        return 0

    logger.info(f"Auto-seeding zone rules for {zone_class} from LAMC Sec. {section_info['section']}")

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
        logger.info(f"LAMC fetch failed for {zone_class}, falling back to LLM knowledge")
        prompt = KNOWLEDGE_PROMPT.format(
            zone_class=zone_class,
            section_number=section_info["section"],
            title=section_info["title"],
        )
        source_note = f"Auto-seeded from LLM knowledge of LAMC Sec. {section_info['section']} (source text unavailable)"

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
            section_number=section_info["section"],
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
