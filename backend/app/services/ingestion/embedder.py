import hashlib
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import RawSource, ParsedRegulation, RegulatoryChunk, IngestionLog
from app.services.ingestion.scraper import scrape_all_sections, LAMC_ZONING_SECTIONS
from app.services.ingestion.parser import parse_html_to_regulations, detect_zone_codes, detect_topic
from app.services.llm.openai_provider import get_llm_service

logger = logging.getLogger(__name__)

REGULATORY_SECTIONS = {
    **{k: v for k, v in LAMC_ZONING_SECTIONS.items()},
    "12.06": {"url": "/lapz/0-0-0-2011", "title": "A2 AGRICULTURAL ZONE", "article": "Article 2"},
    "12.11": {"url": "/lapz/0-0-0-2161", "title": "R4 MULTIPLE DWELLING ZONE", "article": "Article 2"},
    "12.11.5": {"url": "/lapz/0-0-0-2191", "title": "R5 MULTIPLE DWELLING ZONE", "article": "Article 2"},
    "12.12": {"url": "/lapz/0-0-0-2201", "title": "C1 LIMITED COMMERCIAL ZONE", "article": "Article 2"},
    "12.12.5": {"url": "/lapz/0-0-0-2221", "title": "C1.5 LIMITED COMMERCIAL ZONE", "article": "Article 2"},
    "12.13": {"url": "/lapz/0-0-0-2241", "title": "C2 COMMERCIAL ZONE", "article": "Article 2"},
    "12.14": {"url": "/lapz/0-0-0-2271", "title": "C4 COMMERCIAL ZONE", "article": "Article 2"},
    "12.14.5": {"url": "/lapz/0-0-0-2291", "title": "C5 COMMERCIAL ZONE", "article": "Article 2"},
    "12.16": {"url": "/lapz/0-0-0-2321", "title": "CM COMMERCIAL MANUFACTURING ZONE", "article": "Article 2"},
    "12.17": {"url": "/lapz/0-0-0-2341", "title": "M1 LIMITED INDUSTRIAL ZONE", "article": "Article 2"},
    "12.18": {"url": "/lapz/0-0-0-2351", "title": "M2 LIGHT INDUSTRIAL ZONE", "article": "Article 2"},
    "12.19": {"url": "/lapz/0-0-0-2361", "title": "M3 HEAVY INDUSTRIAL ZONE", "article": "Article 2"},
}

SECTION_TO_ZONE_CODES: dict[str, list[str]] = {
    "12.05": ["A1"],
    "12.06": ["A2"],
    "12.07": ["RE", "RE9", "RE11", "RE15", "RE20", "RE40"],
    "12.07.01": ["RS"],
    "12.08": ["R1"],
    "12.08.5": ["RU"],
    "12.09": ["R2"],
    "12.09.5": ["RD", "RD1.5", "RD2", "RD3", "RD4", "RD5", "RD6"],
    "12.10": ["R3"],
    "12.11": ["R4"],
    "12.11.5": ["R5"],
    "12.12": ["C1"],
    "12.12.5": ["C1.5"],
    "12.13": ["C2"],
    "12.14": ["C4"],
    "12.14.5": ["C5"],
    "12.16": ["CM"],
    "12.17": ["M1"],
    "12.18": ["M2"],
    "12.19": ["M3"],
    "12.03": ["GENERAL"],
    "12.04": ["GENERAL"],
    "12.21.1": ["GENERAL"],
    "12.22": ["GENERAL"],
}


def _zone_codes_for_section(section_number: str) -> list[str] | None:
    return SECTION_TO_ZONE_CODES.get(section_number)


LLM_SECTION_PROMPT = """You are a zoning law expert. Generate a comprehensive, accurate regulatory text 
based on your knowledge of Los Angeles Municipal Code (LAMC) Section {section_number} — {title}.

Write the text as if it were the actual code section, covering:
1. Permitted uses and conditional uses
2. Development standards: setbacks (front, side, rear), height limits, floor area ratio, lot area requirements
3. Density limits (lot area per dwelling unit)
4. Parking requirements
5. Lot coverage maximums
6. Special provisions (ADUs, guest houses, specific plan areas)
7. Any exceptions or modifications referenced in Sec. 12.21.1 or 12.22

Structure the output with clear subsections labeled (a), (b), (c), etc.
Use specific numeric values where you know them.
Be thorough — this text will be chunked and used for regulatory retrieval.
Target about 1500-2500 words.

Important: Only include information you are confident about from LAMC."""


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    sentences = []
    current = ""
    for char in text:
        current += char
        if char in ".;:" and len(current.strip()) > 10:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())

    if not sentences:
        return [text] if text.strip() else []

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            words = current_chunk.split()
            overlap_words = words[-max(1, len(words) // 4):]
            current_chunk = " ".join(overlap_words) + " " + sentence
        else:
            current_chunk += (" " if current_chunk else "") + sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


async def run_full_ingestion(db: AsyncSession) -> dict:
    """Run the complete ingestion pipeline: scrape → parse → chunk → embed."""
    llm = get_llm_service()
    stats = {"sections_scraped": 0, "regulations_parsed": 0, "chunks_created": 0}
    log_id = uuid.uuid4()

    log_entry = IngestionLog(
        id=log_id,
        action="initial_ingest",
        new_hash="",
        started_at=datetime.utcnow(),
    )
    db.add(log_entry)

    logger.info("Starting full ingestion pipeline...")

    scraped = await scrape_all_sections()
    stats["sections_scraped"] = len(scraped)

    for section_data in scraped:
        existing = await db.execute(
            select(RawSource).where(
                RawSource.source_url == section_data["url"],
                RawSource.content_hash == section_data["content_hash"],
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"Section {section_data['section_number']} unchanged, skipping")
            continue

        raw_source = RawSource(
            source_url=section_data["url"],
            content_hash=section_data["content_hash"],
            raw_content=section_data["raw_html"],
            content_type="html",
        )
        db.add(raw_source)
        await db.flush()

        regulations = parse_html_to_regulations(
            raw_html=section_data["raw_html"],
            section_number=section_data["section_number"],
            section_title=section_data["title"],
            article=section_data["article"],
            source_url=section_data["url"],
        )

        for reg_data in regulations:
            regulation = ParsedRegulation(
                raw_source_id=raw_source.id,
                section_number=reg_data["section_number"],
                section_title=reg_data["section_title"],
                article=reg_data["article"],
                chapter=reg_data["chapter"],
                zone_codes=reg_data["zone_codes"],
                topic=reg_data["topic"],
                body_text=reg_data["body_text"],
            )
            db.add(regulation)
            await db.flush()
            stats["regulations_parsed"] += 1

            text_chunks = chunk_text(reg_data["body_text"])

            if text_chunks:
                try:
                    embeddings = await llm.embed(text_chunks)
                except Exception as e:
                    logger.error(f"Embedding failed for section {reg_data['section_number']}: {e}")
                    embeddings = [None] * len(text_chunks)

                for idx, (chunk_text_str, embedding) in enumerate(zip(text_chunks, embeddings)):
                    chunk = RegulatoryChunk(
                        regulation_id=regulation.id,
                        chunk_index=idx,
                        chunk_text=chunk_text_str,
                        embedding=embedding,
                        zone_codes=reg_data["zone_codes"],
                        topic=reg_data["topic"],
                        section_number=reg_data["section_number"],
                    )
                    db.add(chunk)
                    stats["chunks_created"] += 1

    log_entry.new_hash = "full_ingestion"
    log_entry.chunks_created = stats["chunks_created"]
    log_entry.completed_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Ingestion complete: {stats}")
    return stats


async def run_llm_ingestion(db: AsyncSession) -> dict:
    """Populate regulatory_chunks using LLM-generated regulatory text.

    Fallback for when amlegal.com scraping is blocked.
    Generates comprehensive regulatory text per LAMC section, then chunks + embeds.
    """
    llm = get_llm_service()
    stats = {"sections_generated": 0, "regulations_created": 0, "chunks_created": 0}
    log_id = uuid.uuid4()

    log_entry = IngestionLog(
        id=log_id,
        action="llm_ingest",
        new_hash="",
        started_at=datetime.utcnow(),
    )
    db.add(log_entry)

    existing_count = (await db.execute(
        select(func.count(RegulatoryChunk.id))
    )).scalar() or 0
    if existing_count > 0:
        logger.info(f"regulatory_chunks already has {existing_count} rows, skipping LLM ingestion")
        log_entry.new_hash = "skipped_existing"
        log_entry.completed_at = datetime.utcnow()
        await db.commit()
        return stats

    logger.info(f"Starting LLM-based ingestion for {len(REGULATORY_SECTIONS)} sections...")

    for section_number, section_info in REGULATORY_SECTIONS.items():
        title = section_info["title"]
        article = section_info["article"]
        source_url = f"https://codelibrary.amlegal.com/codes/los_angeles/latest{section_info['url']}"

        logger.info(f"Generating regulatory text for Sec. {section_number}: {title}")

        try:
            text = await llm.complete(
                messages=[
                    {"role": "system", "content": "You generate accurate Los Angeles Municipal Code regulatory text."},
                    {"role": "user", "content": LLM_SECTION_PROMPT.format(
                        section_number=section_number,
                        title=title,
                    )},
                ],
                temperature=0.0,
                max_tokens=4096,
            )
        except Exception as e:
            logger.error(f"LLM generation failed for {section_number}: {e}")
            continue

        if not text or len(text) < 100:
            logger.warning(f"LLM generated insufficient text for {section_number}")
            continue

        stats["sections_generated"] += 1
        content_hash = hashlib.sha256(text.encode()).hexdigest()

        raw_source = RawSource(
            source_url=source_url,
            content_hash=content_hash,
            raw_content=text,
            content_type="llm",
        )
        db.add(raw_source)
        await db.flush()

        zone_codes = _zone_codes_for_section(section_number) or detect_zone_codes(text, section_number)
        topic = detect_topic(text)

        regulation = ParsedRegulation(
            raw_source_id=raw_source.id,
            section_number=section_number,
            section_title=title,
            article=article,
            chapter="Chapter 1",
            zone_codes=zone_codes,
            topic=topic,
            body_text=text,
        )
        db.add(regulation)
        await db.flush()
        stats["regulations_created"] += 1

        text_chunks = chunk_text(text)

        if text_chunks:
            try:
                embeddings = await llm.embed(text_chunks)
            except Exception as e:
                logger.error(f"Embedding failed for section {section_number}: {e}")
                embeddings = [None] * len(text_chunks)

            for idx, (chunk_str, embedding) in enumerate(zip(text_chunks, embeddings)):
                chunk = RegulatoryChunk(
                    regulation_id=regulation.id,
                    chunk_index=idx,
                    chunk_text=chunk_str,
                    embedding=embedding,
                    zone_codes=zone_codes,
                    topic=topic,
                    section_number=section_number,
                )
                db.add(chunk)
                stats["chunks_created"] += 1

    log_entry.new_hash = "llm_ingestion"
    log_entry.chunks_created = stats["chunks_created"]
    log_entry.completed_at = datetime.utcnow()
    await db.commit()

    logger.info(f"LLM ingestion complete: {stats}")
    return stats
