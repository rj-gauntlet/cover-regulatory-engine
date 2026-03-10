import hashlib
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LAMC_ZONING_SECTIONS = {
    "12.03": {
        "url": "/lapz/0-0-0-1901",
        "title": "DEFINITIONS",
        "article": "Article 2",
    },
    "12.04": {
        "url": "/lapz/0-0-0-1951",
        "title": "USE OF PROPERTY",
        "article": "Article 2",
    },
    "12.05": {
        "url": "/lapz/0-0-0-1971",
        "title": "A1 AGRICULTURAL ZONE",
        "article": "Article 2",
    },
    "12.07": {
        "url": "/lapz/0-0-0-2021",
        "title": "RE RESIDENTIAL ESTATE ZONE",
        "article": "Article 2",
    },
    "12.07.01": {
        "url": "/lapz/0-0-0-2031",
        "title": "RS SUBURBAN ZONE",
        "article": "Article 2",
    },
    "12.08": {
        "url": "/lapz/0-0-0-2052",
        "title": "R1 ONE-FAMILY ZONE",
        "article": "Article 2",
    },
    "12.08.5": {
        "url": "/lapz/0-0-0-2081",
        "title": "RU RESEDA WEST UNIVERSITY ZONE",
        "article": "Article 2",
    },
    "12.09": {
        "url": "/lapz/0-0-0-2091",
        "title": "R2 TWO-FAMILY ZONE",
        "article": "Article 2",
    },
    "12.09.5": {
        "url": "/lapz/0-0-0-2111",
        "title": "RD RESTRICTED DENSITY MULTIPLE DWELLING ZONE",
        "article": "Article 2",
    },
    "12.10": {
        "url": "/lapz/0-0-0-2131",
        "title": "R3 MULTIPLE DWELLING ZONE",
        "article": "Article 2",
    },
    "12.21.1": {
        "url": "/lapz/0-0-0-2371",
        "title": "GENERAL PROVISIONS - RESIDENTIAL ZONES",
        "article": "Article 2",
    },
    "12.22": {
        "url": "/lapz/0-0-0-2481",
        "title": "EXCEPTIONS AND INTERPRETATIONS",
        "article": "Article 2",
    },
}

BASE_URL = "https://codelibrary.amlegal.com/codes/los_angeles/latest"


async def scrape_section(section_number: str) -> dict | None:
    """Scrape a single LAMC section from amlegal.com."""
    section_info = LAMC_ZONING_SECTIONS.get(section_number)
    if not section_info:
        logger.warning(f"Unknown section: {section_number}")
        return None

    url = f"{BASE_URL}{section_info['url']}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None

    content_hash = hashlib.sha256(response.text.encode()).hexdigest()

    return {
        "section_number": section_number,
        "title": section_info["title"],
        "article": section_info["article"],
        "url": url,
        "raw_html": response.text,
        "content_hash": content_hash,
    }


async def scrape_all_sections() -> list[dict]:
    """Scrape all configured LAMC zoning sections."""
    results = []
    for section_number in LAMC_ZONING_SECTIONS:
        result = await scrape_section(section_number)
        if result:
            results.append(result)
            logger.info(f"Scraped section {section_number}: {result['title']}")
    return results
