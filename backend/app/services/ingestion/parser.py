import logging
import re

from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger(__name__)

ZONE_CODE_PATTERNS = {
    "RE": ["RE", "RE9", "RE11", "RE15", "RE20", "RE40"],
    "RS": ["RS"],
    "R1": ["R1", "R1V", "R1F", "R1R", "R1H"],
    "RU": ["RU"],
    "R2": ["R2"],
    "RD": ["RD1.5", "RD2", "RD3", "RD4", "RD5", "RD6"],
    "R3": ["R3"],
}

TOPIC_KEYWORDS = {
    "setback": ["setback", "yard", "front yard", "side yard", "rear yard", "offset"],
    "height": ["height", "stories", "story", "feet high", "encroachment plane"],
    "far": ["floor area", "floor area ratio", "far", "rfar", "residential floor area"],
    "density": ["density", "dwelling unit", "units per", "lot area per"],
    "use": ["permitted use", "conditional use", "prohibited", "accessory", "home occupation"],
    "lot": ["lot area", "lot width", "lot size", "minimum lot"],
    "parking": ["parking", "garage", "automobile"],
    "adu": ["accessory dwelling", "adu", "second unit", "guest house", "granny flat"],
    "coverage": ["lot coverage", "building coverage", "coverage"],
}


def detect_zone_codes(text: str, section_number: str) -> list[str]:
    """Detect which zone codes a regulation section applies to."""
    text_upper = text.upper()

    for section_prefix, codes in [
        ("12.07", ["RE"]),
        ("12.07.01", ["RS"]),
        ("12.08", ["R1"]),
        ("12.08.5", ["RU"]),
        ("12.09", ["R2"]),
        ("12.09.5", ["RD"]),
        ("12.10", ["R3"]),
        ("12.21", ["GENERAL"]),
        ("12.22", ["GENERAL"]),
        ("12.03", ["GENERAL"]),
        ("12.04", ["GENERAL"]),
    ]:
        if section_number.startswith(section_prefix):
            return codes

    found = []
    for zone_family, codes in ZONE_CODE_PATTERNS.items():
        for code in codes:
            if code in text_upper:
                if zone_family not in found:
                    found.append(zone_family)
    return found or ["GENERAL"]


def detect_topic(text: str) -> str:
    """Detect the primary topic of a regulation text block."""
    text_lower = text.lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score

    if scores:
        return max(scores, key=scores.get)
    return "general"


def parse_html_to_regulations(
    raw_html: str,
    section_number: str,
    section_title: str,
    article: str,
    source_url: str,
) -> list[dict]:
    """Parse LAMC HTML into structured regulation records."""
    soup = BeautifulSoup(raw_html, "lxml")

    content = soup.find("div", class_="chunk-content") or soup.find("article") or soup.body
    if not content:
        logger.warning(f"No content found for section {section_number}")
        return []

    for tag in content.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    sections = _split_into_subsections(content, section_number)

    regulations = []
    for sub in sections:
        text = _clean_text(sub["text"])
        if len(text.strip()) < 50:
            continue

        zone_codes = detect_zone_codes(text, section_number)
        topic = detect_topic(text)

        regulations.append({
            "section_number": sub.get("number", section_number),
            "section_title": sub.get("title", section_title),
            "article": article,
            "chapter": "Chapter 1",
            "zone_codes": zone_codes,
            "topic": topic,
            "body_text": text,
            "source_url": source_url,
        })

    if not regulations:
        text = _clean_text(content.get_text())
        if len(text.strip()) >= 50:
            regulations.append({
                "section_number": section_number,
                "section_title": section_title,
                "article": article,
                "chapter": "Chapter 1",
                "zone_codes": detect_zone_codes(text, section_number),
                "topic": detect_topic(text),
                "body_text": text,
                "source_url": source_url,
            })

    return regulations


def _split_into_subsections(content, parent_section: str) -> list[dict]:
    """Split HTML content into logical subsections based on headings."""
    subsections = []
    current = {"number": parent_section, "title": "", "text": ""}

    for element in content.children:
        if isinstance(element, NavigableString):
            current["text"] += str(element)
            continue

        tag_name = getattr(element, "name", None)
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if current["text"].strip():
                subsections.append(current)
            heading_text = element.get_text(strip=True)
            sec_num = _extract_section_number(heading_text) or parent_section
            current = {
                "number": sec_num,
                "title": heading_text,
                "text": "",
            }
        else:
            current["text"] += element.get_text(separator=" ") + "\n"

    if current["text"].strip():
        subsections.append(current)

    return subsections


def _extract_section_number(text: str) -> str | None:
    """Extract a section number like '12.08' or 'SEC. 12.08.A' from heading text."""
    match = re.search(r"(?:SEC\.?\s*)?(\d{2}\.\d{2}(?:\.\d+)?(?:\.[A-Z])?)", text, re.IGNORECASE)
    return match.group(1) if match else None


def _clean_text(text: str) -> str:
    """Clean extracted text by normalizing whitespace."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()
